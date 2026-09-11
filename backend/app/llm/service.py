import base64
import re

from openai import RateLimitError

from app.core.config import get_settings
from app.llm.providers import azure_openai, groq

SYSTEM_PROMPT = """You are an AI Browser Agent: an assistant embedded in the user's browser that can \
read the page they are currently looking at and answer questions about it.

You are given:
- The page URL and title
- The visible text content of the page
- Optionally, a screenshot of the page
- Optionally, a short prior conversation about this same page

If the user is asking about the page (summarizing, extracting, explaining, comparing, etc.), \
answer using only the page content provided - if the answer isn't there, say so plainly instead \
of guessing. Be concise and direct, and quote or reference the specific part of the page you're \
basing your answer on when useful.

If the user is just greeting you or making small talk unrelated to the page, respond naturally \
and briefly instead of commenting on the page content."""


def _validate_data_url(data_url: str) -> None:
    match = re.match(r"^data:image/\w+;base64,(.+)$", data_url, re.DOTALL)
    if not match:
        raise ValueError("screenshot must be a base64 data URL (data:image/...;base64,...)")
    base64.b64decode(match.group(1), validate=True)


def _build_messages(
    *,
    question: str,
    url: str,
    title: str,
    page_text: str,
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
                f"User question: {question}"
            ),
        }
    ]

    if include_image and screenshot_data_url:
        content.append({"type": "image_url", "image_url": {"url": screenshot_data_url}})

    messages = [{"role": turn["role"], "content": turn["content"]} for turn in history]
    messages.append({"role": "user", "content": content})
    return messages


def answer_page_question(
    *,
    question: str,
    url: str,
    title: str,
    page_text: str,
    screenshot_data_url: str | None = None,
    history: list[dict[str, str]] | None = None,
) -> str:
    settings = get_settings()
    if screenshot_data_url:
        _validate_data_url(screenshot_data_url)

    history = history or []

    if not settings.azure_configured and not settings.groq_configured:
        raise ValueError(
            "No LLM provider is configured on the backend "
            "(set AZURE_LLM_* or GROQ_API_KEY - see backend/.env.example)"
        )

    if settings.azure_configured:
        try:
            messages = _build_messages(
                question=question,
                url=url,
                title=title,
                page_text=page_text,
                screenshot_data_url=screenshot_data_url,
                history=history,
                include_image=True,
            )
            return azure_openai.chat(system=SYSTEM_PROMPT, messages=messages)
        except RateLimitError:
            if not settings.groq_configured:
                raise

    # Fallback path: Groq is text-only, so the screenshot (if any) is dropped.
    system = SYSTEM_PROMPT
    if screenshot_data_url:
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
        screenshot_data_url=None,
        history=history,
        include_image=False,
    )
    return groq.chat(system=system, messages=messages)
