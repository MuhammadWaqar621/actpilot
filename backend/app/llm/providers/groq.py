import time
from functools import lru_cache

from openai import OpenAI, RateLimitError

from app.core.config import get_settings

GROQ_BASE_URL = "https://api.groq.com/openai/v1"

# Groq enforces quota per model independently, so if the configured model's
# limit is hit, a different model can still have budget left. Same pattern
# as the private-document-assistant project's groq_client.py.
FALLBACK_MODELS = ["qwen/qwen3.8-27b", "openai/gpt-oss-20b"]

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


def chat(*, system: str, messages: list[dict]) -> str:
    settings = get_settings()
    client = get_client()

    last_exc: Exception | None = None
    for model in _live_model_chain(settings.groq_llm_model, client):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": system}, *messages],
                max_tokens=1024,
            )
            return response.choices[0].message.content or ""
        except RateLimitError as exc:
            last_exc = exc
            continue

    raise last_exc or RuntimeError("No Groq chat model available")
