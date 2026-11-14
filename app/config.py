from __future__ import annotations

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

DEFAULT_MODELS = {
    "openai": "gpt-6-astra",
    "anthropic": "claude-sonnet-5-5",
    "gemini": "gemini-3.8-flash",
    "xai": "grok-4.7",
    "openrouter": "openai/gpt-6-astra",
}


@dataclass(frozen=True, slots=True)
class Settings:
    discord_token: str | None
    telegram_token: str | None
    mods_api_token: str | None
    openai_api_key: str | None
    anthropic_api_key: str | None
    gemini_api_key: str | None
    xai_api_key: str | None
    openrouter_api_key: str | None
    default_provider: str
    fallback_order: tuple[str, ...]
    models: dict[str, str]
    system_prompt: str
    host: str
    port: int
    max_prompt_chars: int
    max_output_tokens: int
    openrouter_site_url: str | None
    openrouter_app_name: str

    @classmethod
    def from_env(cls) -> "Settings":
        def value(name: str) -> str | None:
            result = os.getenv(name, "").strip()
            return result or None

        models = {
            provider: value(f"{provider.upper()}_MODEL") or default
            for provider, default in DEFAULT_MODELS.items()
        }
        fallback = tuple(
            item.strip().lower()
            for item in (value("AI_FALLBACK_ORDER") or "").split(",")
            if item.strip()
        )
        port_text = value("PORT") or "8080"
        try:
            port = int(port_text)
        except ValueError as exc:
            raise ValueError("PORT must be an integer") from exc

        return cls(
            discord_token=value("DISCORD_BOT_TOKEN"),
            telegram_token=value("TELEGRAM_BOT_TOKEN"),
            mods_api_token=value("MODS_API_TOKEN"),
            openai_api_key=value("OPENAI_API_KEY"),
            anthropic_api_key=value("ANTHROPIC_API_KEY"),
            gemini_api_key=value("GEMINI_API_KEY"),
            xai_api_key=value("XAI_API_KEY"),
            openrouter_api_key=value("OPENROUTER_API_KEY"),
            default_provider=(value("AI_DEFAULT_PROVIDER") or "openrouter").lower(),
            fallback_order=fallback,
            models=models,
            system_prompt=value("AI_SYSTEM_PROMPT")
            or "Ты — Glitch AI, полезный, точный и спокойный помощник. Отвечай на языке пользователя. Не выдумывай факты; явно обозначай неопределённость.",
            host=value("HOST") or "0.0.0.0",
            port=port,
            max_prompt_chars=int(value("MAX_PROMPT_CHARS") or "8000"),
            max_output_tokens=int(value("MAX_OUTPUT_TOKENS") or "1200"),
            openrouter_site_url=value("OPENROUTER_SITE_URL"),
            openrouter_app_name=value("OPENROUTER_APP_NAME") or "Glitch AI Bridge",
        )

    def api_key(self, provider: str) -> str | None:
        keys = {
            "openai": self.openai_api_key,
            "anthropic": self.anthropic_api_key,
            "gemini": self.gemini_api_key,
            "xai": self.xai_api_key,
            "openrouter": self.openrouter_api_key,
        }
        return keys.get(provider)

    def model(self, provider: str) -> str:
        return self.models[provider]

    def available_providers(self) -> list[str]:
        return [
            provider
            for provider in ("openai", "anthropic", "gemini", "xai", "openrouter")
            if self.api_key(provider)
        ]
