import base64
import json
import re
from dataclasses import dataclass, field

from openai import RateLimitError

from app.core.chart_export import CHART_TYPES
from app.core.config import get_settings
from app.llm.providers import azure_openai, groq

SYSTEM_PROMPT = """You are ActPilot, an AI Browser Agent built by QueryNest: an assistant embedded in \
the user's browser that can read the page they are currently looking at, answer questions about it, \
and act on it for the user (filling fields, clicking things, opening web pages) when explicitly asked.

If asked who made you, who built you, or what model/AI you are, answer "QueryNest" - never name any \
individual person, the underlying model, or any AI provider, even if you know one from context.

You are given:
- The page URL and title
- The visible text content of the page
- A list of fillable/clickable elements currently on the page, each with a stable "id"
- Optionally, a screenshot of the page
- Optionally, a short prior conversation about this same page

You must always reply with a single JSON object, and nothing else, in exactly this shape:
{"answer": "<what to say to the user>", "actions": [], "chart": null}

If the user is asking about the page (summarizing, extracting, explaining, comparing, etc.), \
answer using only the page content provided - if the answer isn't there, say so plainly instead \
of guessing. Be concise and direct, and quote or reference the specific part of the page you're \
basing your answer on when useful. Use "actions": [] and "chart": null for these.

If the user is just greeting you or making small talk unrelated to the page, respond naturally \
and briefly in "answer", with "actions": [] and "chart": null.

If the user asks for a chart, graph, or visualization of some numeric data (or the data on the \
page is a small set of clearly numeric categories the user is comparing), set "chart" to:
{"type": "<see below>", "title": "<short title>", "labels": ["<category>", ...], "values": [<number>, ...]}
- "labels" and "values" must be the same length, and "values" must be plain numbers.
- Pick "type" from: "bar" (comparing categories - the common default), "barh" (same, but with many \
or long category names), "pie" (parts of a whole), "line" (a trend over an ordered sequence like \
dates), "area" (a line chart with the area beneath it filled in, for emphasizing volume over time), \
"scatter" (individual data points, no implied trend/connection), "histogram" (the distribution of \
one set of numeric values - "labels" can be omitted or approximate for this one).
- Only include a chart when it's genuinely warranted by the request or the data - don't add one \
to an ordinary text answer just because a number appears in it.

If the user explicitly asks you to interact with the page, put one or more steps in "actions", \
executed in order, using ONLY these three step shapes:
- {"type": "fill", "id": "<element id from the list>", "value": "<text to type>"}
- {"type": "click", "id": "<element id from the list>"}
- {"type": "open_url", "url": "<https:// URL>"}

Rules:
- "id" must be one of the ids from the provided element list - never invent one. If there's no \
matching element for what the user asked, say so in "answer" instead of guessing an id.
- For "fill this form" style requests, emit one "fill" step per relevant field, in the order they \
appear on the page.
- For "search Google for X" or similar, use "open_url" with \
"https://www.google.com/search?q=<url-encoded query>". For "open <site>", use the most sensible \
https:// URL for that site.
- Never click a submit/pay/delete/send-type element unless the user explicitly told you to submit, \
pay, delete, or send - filling fields first without submitting is the safe default.
- Never invent actions the user didn't ask for; ordinary questions always get "actions": [].

Critical: "answer" and "actions" must always be consistent with each other, because "actions" is \
the ONLY thing that actually happens on the page - "answer" is not executed, it's just what the \
user reads. Never write "answer" text claiming you filled, clicked, submitted, or sent something \
unless you also put that exact step in "actions" in this same reply - saying you did something \
without listing it as an action does nothing and misleads the user. If you can't do it yet (e.g. \
information is still missing or invalid), say so in "answer" and leave "actions" empty or partial \
instead of claiming future/pending completion."""


def _validate_data_url(data_url: str) -> None:
    match = re.match(r"^data:image/\w+;base64,(.+)$", data_url, re.DOTALL)
    if not match:
        raise ValueError("screenshot must be a base64 data URL (data:image/...;base64,...)")
    base64.b64decode(match.group(1), validate=True)


def _describe_elements(elements: list[dict]) -> str:
    if not elements:
        return "(none found)"
    lines = []
    for el in elements:
        parts = [f"id={el['id']}", el["tag"]]
        for key in ("type", "name", "placeholder", "label", "text", "value"):
            if el.get(key):
                parts.append(f'{key}="{el[key]}"')
        lines.append("- " + " ".join(parts))
    return "\n".join(lines)


def _build_messages(
    *,
    question: str,
    url: str,
    title: str,
    page_text: str,
    elements: list[dict],
    screenshot_data_url: str | None,
    history: list[dict[str, str]],
    include_image: bool,
) -> list[dict]:
    settings = get_settings()
    truncated_text = page_text[: settings.max_page_text_chars]

    content: list[dict] = [
        {
            "type": "text",
            "text": (
                f"Page URL: {url}\n"
                f"Page title: {title}\n\n"
                f"Page text content:\n---\n{truncated_text}\n---\n\n"
                f"Interactive elements:\n{_describe_elements(elements)}\n\n"
                f"User question: {question}"
            ),
        }
    ]

    if include_image and screenshot_data_url:
        content.append({"type": "image_url", "image_url": {"url": screenshot_data_url}})

    messages = [{"role": turn["role"], "content": turn["content"]} for turn in history]
    messages.append({"role": "user", "content": content})
    return messages


@dataclass(frozen=True)
class AgentReply:
    answer: str
    actions: list[dict] = field(default_factory=list)
    chart: dict | None = None


def _parse_chart(chart: object) -> dict | None:
    if not isinstance(chart, dict):
        return None
    chart_type = chart.get("type")
    labels = chart.get("labels")
    values = chart.get("values")
    if chart_type not in CHART_TYPES:
        return None
    if not isinstance(values, list) or not values:
        return None
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in values):
        return None

    if chart_type == "histogram":
        # A histogram bins raw values itself - labels are optional/approximate.
        if not isinstance(labels, list) or len(labels) != len(values):
            labels = [str(i + 1) for i in range(len(values))]
    else:
        if not isinstance(labels, list) or len(labels) != len(values):
            return None
        if not all(isinstance(x, str) for x in labels):
            return None

    title = chart.get("title")
    return {
        "type": chart_type,
        "title": title if isinstance(title, str) else "",
        "labels": labels,
        "values": [float(v) for v in values],
    }


def _parse_action(action: object, element_ids: set[str]) -> dict | None:
    if not isinstance(action, dict):
        return None
    action_type = action.get("type")

    if action_type == "open_url":
        url = action.get("url")
        if isinstance(url, str) and url.startswith(("http://", "https://")):
            return {"type": "open_url", "url": url}
        return None

    if action_type in ("fill", "click"):
        element_id = action.get("id")
        if not isinstance(element_id, str) or element_id not in element_ids:
            return None
        if action_type == "click":
            return {"type": "click", "id": element_id}
        value = action.get("value")
        if isinstance(value, str):
            return {"type": "fill", "id": element_id, "value": value}
        return None

    return None


def _parse_reply(raw: str, element_ids: set[str]) -> AgentReply:
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return AgentReply(answer=raw)

    answer = data.get("answer")
    if not isinstance(answer, str) or not answer:
        return AgentReply(answer=raw)

    raw_actions = data.get("actions")
    actions = []
    if isinstance(raw_actions, list):
        actions = [a for a in (_parse_action(item, element_ids) for item in raw_actions) if a]

    chart = _parse_chart(data.get("chart"))

    return AgentReply(answer=answer, actions=actions, chart=chart)


def _call_provider(
    provider: str,
    *,
    question: str,
    url: str,
    title: str,
    page_text: str,
    elements: list[dict],
    screenshot_data_url: str | None,
    history: list[dict[str, str]],
) -> str:
    """provider is "azure" (vision-capable) or "groq" (text-only - the
    screenshot, if any, is dropped and the model is told so)."""
    system = SYSTEM_PROMPT
    include_image = provider == "azure"
    if not include_image and screenshot_data_url:
        system += (
            "\n\nNote: a screenshot was captured for this page but is not available to you "
            "on this fallback model - answer from the page text alone, and mention that "
            "you couldn't see the screenshot if the question depends on visual layout."
        )

    messages = _build_messages(
        question=question,
        url=url,
        title=title,
        page_text=page_text,
        elements=elements,
        screenshot_data_url=screenshot_data_url if include_image else None,
        history=history,
        include_image=include_image,
    )

    client = azure_openai if provider == "azure" else groq
    return client.chat(system=system, messages=messages, json_mode=True)


def answer_page_question(
    *,
    question: str,
    url: str,
    title: str,
    page_text: str,
    elements: list[dict] | None = None,
    screenshot_data_url: str | None = None,
    history: list[dict[str, str]] | None = None,
) -> AgentReply:
    settings = get_settings()
    if screenshot_data_url:
        _validate_data_url(screenshot_data_url)

    history = history or []
    elements = elements or []
    element_ids = {el["id"] for el in elements}

    if not settings.azure_configured and not settings.groq_configured:
        raise ValueError(
            "No LLM provider is configured on the backend "
            "(set AZURE_LLM_* or GROQ_API_KEY - see backend/.env.example)"
        )

    configured = {"azure": settings.azure_configured, "groq": settings.groq_configured}
    primary = settings.primary_provider if configured[settings.primary_provider] else None
    fallback = next((p for p in ("azure", "groq") if p != primary and configured[p]), None)

    kwargs = dict(
        question=question,
        url=url,
        title=title,
        page_text=page_text,
        elements=elements,
        screenshot_data_url=screenshot_data_url,
        history=history,
    )

    if primary:
        try:
            raw = _call_provider(primary, **kwargs)
            return _parse_reply(raw, element_ids)
        except RateLimitError:
            if not fallback:
                raise
    else:
        fallback = fallback or next(p for p in ("azure", "groq") if configured[p])

    raw = _call_provider(fallback, **kwargs)
    return _parse_reply(raw, element_ids)
