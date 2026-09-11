import base64
import re

from anthropic import Anthropic

from app.core.config import get_settings

SYSTEM_PROMPT = """You are an AI Browser Agent: an assistant embedded in the user's browser that can \
read the page they are currently looking at and answer questions about it.

You are given:
- The page URL and title
- The visible text content of the page
- Optionally, a screenshot of the page
- Optionally, a short prior conversation about this same page

Answer the user's question using only the page content provided. If the answer isn't in the page, \
say so plainly instead of guessing. Be concise and direct. When useful, quote or reference the \
specific part of the page you're basing your answer on."""


def _extract_data_url(data_url: str) -> tuple[str, str]:
    match = re.match(r"^data:(image/\w+);base64,(.+)$", data_url, re.DOTALL)
    if not match:
        raise ValueError("screenshot must be a base64 data URL (data:image/...;base64,...)")
    media_type, b64_data = match.group(1), match.group(2)
    base64.b64decode(b64_data, validate=True)
    return media_type, b64_data


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
    client = Anthropic(api_key=settings.anthropic_api_key)

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

    if screenshot_data_url:
        media_type, b64_data = _extract_data_url(screenshot_data_url)
        content.insert(
            0,
            {
                "type": "image",
                "source": {"type": "base64", "media_type": media_type, "data": b64_data},
            },
        )

    messages: list[dict] = list(history or [])
    messages.append({"role": "user", "content": content})

    response = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=messages,
    )

    return "".join(block.text for block in response.content if block.type == "text")
