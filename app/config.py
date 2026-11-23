from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlsplit

from dotenv import load_dotenv

load_dotenv()

DEFAULT_MODELS = {
    "openai": "gpt-6-astra",
    "anthropic": "claude-sonnet-5-5",
    "gemini": "gemini-3.8-flash",
    "xai": "grok-4.7",
    "openrouter": "openrouter/free",
    "groq": "qwen/qwen3.8-27b",
    "deepseek": "deepseek-flash",
    "mistral": "mistral-large-latest",
    "cloudflare": "@cf/meta/llama-3.1-8b-instruct",
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
    groq_api_key: str | None
    deepseek_api_key: str | None
    mistral_api_key: str | None
    cloudflare_api_token: str | None
    cloudflare_account_id: str | None
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
    custom_openai_api_key: str | None
    custom_openai_base_url: str | None
    custom_openai_allow_insecure_http: bool
    mcp_enabled: bool
    mcp_api_token: str | None
    mcp_host: str
    mcp_port: int
    max_concurrent_ai_requests: int
    request_timeout_seconds: int
    requests_per_minute: int

    @classmethod
    def from_env(cls) -> "Settings":
        def value(name: str) -> str | None:
            result = os.getenv(name, "").strip()
            return result or None

        def integer(name: str, default: int, minimum: int, maximum: int) -> int:
            raw = value(name)
            try:
                result = int(raw) if raw is not None else default
            except ValueError as exc:
                raise ValueError(f"{name} must be an integer") from exc
            if not minimum <= result <= maximum:
                raise ValueError(f"{name} must be between {minimum} and {maximum}")
            return result

        models = {
            provider: value(f"{provider.upper()}_MODEL") or default
            for provider, default in DEFAULT_MODELS.items()
        }
        models["custom"] = value("CUSTOM_OPENAI_MODEL") or "local-model"

        fallback = tuple(
            item.strip().lower()
            for item in (value("AI_FALLBACK_ORDER") or "").split(",")
            if item.strip()
        )

        port = integer("PORT", 8080, 1, 65535)
        mcp_port = integer("MCP_PORT", 8081, 1, 65535)
        custom_base_url = value("CUSTOM_OPENAI_BASE_URL")
        allow_insecure_custom_http = (
            (value("CUSTOM_OPENAI_ALLOW_INSECURE_HTTP") or "false").lower()
            in {"1", "true", "yes", "on"}
        )

        if custom_base_url:
            parsed = urlsplit(custom_base_url)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError(
                    "CUSTOM_OPENAI_BASE_URL must be an HTTP(S) URL without credentials, query, or fragment"
                )
            if (
                parsed.scheme == "http"
                and parsed.hostname.lower() not in {"localhost", "127.0.0.1", "::1"}
                and not allow_insecure_custom_http
            ):
                raise ValueError(
                    "Remote custom providers must use HTTPS; set CUSTOM_OPENAI_ALLOW_INSECURE_HTTP=true only on a trusted private network"
                )

        mcp_enabled = (
            (value("MCP_ENABLED") or "false").lower() in {"1", "true", "yes", "on"}
        )
        mcp_api_token = value("MCP_API_TOKEN")
        mcp_host = (value("MCP_HOST") or "127.0.0.1").lower()
        if mcp_enabled and not mcp_api_token:
            raise ValueError("MCP_API_TOKEN is required when MCP_ENABLED=true")
        if mcp_enabled and mcp_host not in {"127.0.0.1", "localhost"}:
            raise ValueError(
                "MCP_HOST must be 127.0.0.1 or localhost. Expose remote MCP access "
                "only through a separately configured HTTPS reverse proxy."
            )

        provider_keys = {
            "openai": value("OPENAI_API_KEY"),
            "anthropic": value("ANTHROPIC_API_KEY"),
            "gemini": value("GEMINI_API_KEY"),
            "xai": value("XAI_API_KEY"),
            "openrouter": value("OPENROUTER_API_KEY"),
            "groq": value("GROQ_API_KEY"),
            "deepseek": value("DEEPSEEK_API_KEY"),
            "mistral": value("MISTRAL_API_KEY"),
            "cloudflare": value("CLOUDFLARE_API_TOKEN"),
        }
        cloudflare_account_id = value("CLOUDFLARE_ACCOUNT_ID")
        configured = [
            name for name, key in provider_keys.items()
            if key and (name != "cloudflare" or cloudflare_account_id)
        ]
        if custom_base_url:
            configured.append("custom")

        requested_provider = value("AI_DEFAULT_PROVIDER")
        default_provider = (
            requested_provider.lower()
            if requested_provider
            else (
                "openrouter"
                if provider_keys["openrouter"]
                else configured[0] if configured else "openrouter"
            )
        )

        return cls(
            discord_token=value("DISCORD_BOT_TOKEN"),
            telegram_token=value("TELEGRAM_BOT_TOKEN"),
            mods_api_token=value("MODS_API_TOKEN"),
            openai_api_key=provider_keys["openai"],
            anthropic_api_key=provider_keys["anthropic"],
            gemini_api_key=provider_keys["gemini"],
            xai_api_key=provider_keys["xai"],
            openrouter_api_key=provider_keys["openrouter"],
            groq_api_key=provider_keys["groq"],
            deepseek_api_key=provider_keys["deepseek"],
            mistral_api_key=provider_keys["mistral"],
            cloudflare_api_token=provider_keys["cloudflare"],
            cloudflare_account_id=cloudflare_account_id,
            default_provider=default_provider,
            fallback_order=fallback,
            models=models,
            system_prompt=value("AI_SYSTEM_PROMPT")
            or "Ты — Glitch AI, полезный, точный и спокойный помощник. Отвечай на языке пользователя. Не выдумывай факты; явно обозначай неопределённость.",
            host=value("HOST") or "0.0.0.0",
            port=port,
            max_prompt_chars=integer("MAX_PROMPT_CHARS", 8000, 256, 100000),
            max_output_tokens=integer("MAX_OUTPUT_TOKENS", 1200, 64, 32000),
            openrouter_site_url=value("OPENROUTER_SITE_URL"),
            openrouter_app_name=value("OPENROUTER_APP_NAME") or "Glitch AI Bridge",
            custom_openai_api_key=value("CUSTOM_OPENAI_API_KEY"),
            custom_openai_base_url=custom_base_url.rstrip("/") if custom_base_url else None,
            custom_openai_allow_insecure_http=allow_insecure_custom_http,
            mcp_enabled=mcp_enabled,
            mcp_api_token=mcp_api_token,
            mcp_host=mcp_host,
            mcp_port=mcp_port,
            max_concurrent_ai_requests=integer("MAX_CONCURRENT_AI_REQUESTS", 2, 1, 8),
            request_timeout_seconds=integer("AI_REQUEST_TIMEOUT_SECONDS", 45, 5, 180),
            requests_per_minute=integer("AI_REQUESTS_PER_MINUTE", 8, 1, 120),
        )

    def api_key(self, provider: str) -> str | None:
        keys = {
            "openai": self.openai_api_key,
            "anthropic": self.anthropic_api_key,
            "gemini": self.gemini_api_key,
            "xai": self.xai_api_key,
            "openrouter": self.openrouter_api_key,
            "groq": self.groq_api_key,
            "deepseek": self.deepseek_api_key,
            "mistral": self.mistral_api_key,
            "cloudflare": self.cloudflare_api_token if self.cloudflare_account_id else None,
            "custom": self.custom_openai_api_key,
        }
        return keys.get(provider)

    def model(self, provider: str) -> str:
        return self.models[provider]

    def available_providers(self) -> list[str]:
        providers = [
            provider
            for provider in (
                "openai", "anthropic", "gemini", "xai", "openrouter",
                "groq", "deepseek", "mistral", "cloudflare",
            )
            if self.api_key(provider)
        ]
        if self.custom_openai_base_url:
            providers.append("custom")
        return providers
