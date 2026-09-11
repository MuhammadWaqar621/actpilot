from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_CHAT_API_VERSION = "2024-08-01-preview"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Primary chat provider: Azure OpenAI (vision-capable - needed to read
    # the page screenshot). Falls back to Groq automatically on rate-limit.
    azure_llm_endpoint: str = ""
    azure_llm_api_key: str = ""
    azure_llm_model: str = "gpt-4o-mini"
    azure_llm_api_version: str = DEFAULT_CHAT_API_VERSION

    # Fallback chat provider: Groq (OpenAI-compatible API). Text-only - no
    # screenshot support - so the screenshot is dropped when this is used.
    groq_api_key: str = ""
    groq_llm_model: str = "openai/gpt-oss-120b"

    cors_allow_origins: str = "*"
    max_page_text_chars: int = 12000

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]

    @property
    def azure_configured(self) -> bool:
        return bool(self.azure_llm_endpoint and self.azure_llm_api_key and self.azure_llm_model)

    @property
    def groq_configured(self) -> bool:
        return bool(self.groq_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
