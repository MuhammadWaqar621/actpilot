from functools import lru_cache

from openai import AzureOpenAI

from app.core.config import get_settings


@lru_cache
def get_client() -> AzureOpenAI:
    settings = get_settings()
    return AzureOpenAI(
        azure_endpoint=settings.azure_llm_endpoint,
        api_key=settings.azure_llm_api_key,
        api_version=settings.azure_llm_api_version,
    )


def chat(*, system: str, messages: list[dict]) -> str:
    settings = get_settings()
    client = get_client()
    response = client.chat.completions.create(
        model=settings.azure_llm_model,
        messages=[{"role": "system", "content": system}, *messages],
        max_tokens=1024,
    )
    return response.choices[0].message.content or ""
