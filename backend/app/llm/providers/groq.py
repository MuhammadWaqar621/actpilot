import time
from functools import lru_cache

from openai import OpenAI, RateLimitError

from app.core.config import get_settings

GROQ_BASE_URL = "https://api.groq.com/openai/v1"

# Groq enforces quota per model independently, so if the configured model's
# limit is hit, a different model can still have budget left.
#
# This list is vetted against ActPilot's OWN prompt (strict JSON with
# string-typed element ids for fill/click actions), not just copied from
# another project's chat-only vetting - tested live against
# app.llm.service.SYSTEM_PROMPT on 2026-09-11:
#   - openai/gpt-oss-20b, qwen/qwen3.6-27b: correct JSON, string ids - kept.
#   - qwen/qwen3.8-27b: returned {"id": 0} (a number, not a string) for
#     fill/click actions, which our schema validation then silently drops -
#     the model "looks broken" here even though it's fine for plain chat.
#     Excluded.
#   - groq/compound, groq/compound-mini: correct JSON, but "compound" runs
#     on top of gpt-oss-120b internally and shares its quota rather than
#     having an independent one, so it isn't a real fallback. Excluded.
FALLBACK_MODELS = ["openai/gpt-oss-20b", "qwen/qwen3.6-27b"]

_MODEL_LIST_TTL_SECONDS = 3600
_model_list_cache: set[str] = set()
_model_list_cached_at: float = 0.0


@lru_cache
def get_client() -> OpenAI:
    settings = get_settings()
    return OpenAI(api_key=settings.groq_api_key, base_url=GROQ_BASE_URL)


def _live_model_chain(primary: str, client: OpenAI) -> list[str]:
    global _model_list_cache, _model_list_cached_at  # noqa: PLW0603

    vetted = list(dict.fromkeys([primary, *FALLBACK_MODELS]))
    now = time.monotonic()
    if not _model_list_cache or (now - _model_list_cached_at) > _MODEL_LIST_TTL_SECONDS:
        try:
            live = client.models.list()
            _model_list_cache = {m.id for m in live.data}
            _model_list_cached_at = now
        except Exception:  # noqa: BLE001 - listing failed, use whatever we had
            if not _model_list_cache:
                return vetted

    chain = [m for m in vetted if m in _model_list_cache]
    return chain or vetted


def chat(*, system: str, messages: list[dict], json_mode: bool = False) -> str:
    settings = get_settings()
    client = get_client()
    extra = {"response_format": {"type": "json_object"}} if json_mode else {}

    last_exc: Exception | None = None
    for model in _live_model_chain(settings.groq_llm_model, client):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": system}, *messages],
                max_tokens=1024,
                **extra,
            )
            return response.choices[0].message.content or ""
        except RateLimitError as exc:
            last_exc = exc
            continue

    raise last_exc or RuntimeError("No Groq chat model available")
