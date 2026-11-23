from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
import pytest

from app.config import DEFAULT_MODELS, Settings
from app.providers import ProviderGateway


def settings_for(monkeypatch: pytest.MonkeyPatch, provider: str) -> Settings:
    names = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "gemini": "GEMINI_API_KEY",
        "xai": "XAI_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
        "groq": "GROQ_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
        "mistral": "MISTRAL_API_KEY",
        "cloudflare": "CLOUDFLARE_API_TOKEN",
        "nvidia": "NVIDIA_API_KEY",
        "cohere": "COHERE_API_KEY",
        "sensenova": "SENSENOVA_API_KEY",
    }
    for env_name in names.values():
        monkeypatch.delenv(env_name, raising=False)
    monkeypatch.setenv(names[provider], "unit-test-token")
    if provider == "cloudflare":
        monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "test-account")
    else:
        monkeypatch.delenv("CLOUDFLARE_ACCOUNT_ID", raising=False)
    monkeypatch.delenv("SENSENOVA_BASE_URL", raising=False)
    if provider == "sensenova":
        monkeypatch.setenv("SENSENOVA_BASE_URL", "https://token.sensenova.ai/v1")
    monkeypatch.setenv("AI_DEFAULT_PROVIDER", provider)
    monkeypatch.delenv("AI_FALLBACK_ORDER", raising=False)
    return Settings.from_env()


def run_gateway(
    settings: Settings,
    handler: Any,
    messages: list[dict[str, str]] | None = None,
) -> tuple[str, str]:
    async def execute() -> tuple[str, str]:
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        gateway = ProviderGateway(settings, client=client)
        try:
            return await gateway.complete(
                messages or [{"role": "user", "content": "Проверь запрос"}]
            )
        finally:
            await client.aclose()

    return asyncio.run(execute())


def test_current_default_model_ids() -> None:
    assert DEFAULT_MODELS == {
        "openai": "gpt-6-astra",
        "anthropic": "claude-sonnet-5-5",
        "gemini": "gemini-3.8-flash",
        "xai": "grok-4.7",
        "openrouter": "openrouter/free",
        "groq": "qwen/qwen3.8-27b",
        "deepseek": "deepseek-flash",
        "mistral": "mistral-large-latest",
        "cloudflare": "@cf/zai-org/glm-4.7-flash",
        "nvidia": "deepseek-ai/deepseek-v4-flash",
        "cohere": "command-a-plus-05-2026",
        "sensenova": "sensenova-6.8-flash-lite",
    }


def test_openai_responses_request_uses_string_message_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = settings_for(monkeypatch, "openai")
    seen: dict[str, Any] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["authorization"] = request.headers.get("Authorization")
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": "Готово"}],
                    }
                ]
            },
        )

    provider, answer = run_gateway(
        settings,
        handler,
        [
            {"role": "user", "content": "Привет"},
            {"role": "assistant", "content": "Здравствуйте"},
            {"role": "user", "content": "Продолжим"},
        ],
    )

    assert (provider, answer) == ("openai", "Готово")
    assert seen["url"] == "https://api.openai.com/v1/responses"
    assert seen["authorization"] == "Bearer unit-test-token"
    assert seen["body"]["model"] == "gpt-6-astra"
    assert seen["body"]["input"][1] == {
        "role": "assistant",
        "content": "Здравствуйте",
    }
    assert seen["body"]["max_output_tokens"] == settings.max_output_tokens


@pytest.mark.parametrize(
    ("provider_name", "expected_url", "response_body"),
    [
        (
            "anthropic",
            "https://api.anthropic.com/v1/messages",
            {"content": [{"type": "text", "text": "Claude ответ"}]},
        ),
        (
            "gemini",
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent",
            {
                "candidates": [
                    {"content": {"parts": [{"text": "Gemini ответ"}]}}
                ]
            },
        ),
        (
            "xai",
            "https://api.x.ai/v1/chat/completions",
            {"choices": [{"message": {"content": "Grok ответ"}}]},
        ),
        (
            "openrouter",
            "https://openrouter.ai/api/v1/chat/completions",
            {"choices": [{"message": {"content": "OpenRouter ответ"}}]},
        ),
        (
            "groq",
            "https://api.groq.com/openai/v1/chat/completions",
            {"choices": [{"message": {"content": "Groq ответ"}}]},
        ),
        (
            "deepseek",
            "https://api.deepseek.com/chat/completions",
            {"choices": [{"message": {"content": "DeepSeek ответ"}}]},
        ),
        (
            "mistral",
            "https://api.mistral.ai/v1/chat/completions",
            {"choices": [{"message": {"content": "Mistral ответ"}}]},
        ),
        (
            "cloudflare",
            "https://api.cloudflare.com/client/v4/accounts/test-account/ai/v1/chat/completions",
            {"choices": [{"message": {"content": "Cloudflare ответ"}}]},
        ),
        (
            "nvidia",
            "https://integrate.api.nvidia.com/v1/chat/completions",
            {"choices": [{"message": {"content": "NVIDIA ответ"}}]},
        ),
        (
            "cohere",
            "https://api.cohere.com/v2/chat",
            {"message": {"content": [{"type": "text", "text": "Cohere ответ"}]}},
        ),
        (
            "sensenova",
            "https://token.sensenova.ai/v1/chat/completions",
            {"choices": [{"message": {"content": "SenseNova ответ"}}]},
        ),
    ],
)
def test_provider_endpoint_headers_and_payload(
    monkeypatch: pytest.MonkeyPatch,
    provider_name: str,
    expected_url: str,
    response_body: dict[str, Any],
) -> None:
    settings = settings_for(monkeypatch, provider_name)
    seen: dict[str, Any] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["headers"] = dict(request.headers)
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=response_body)

    provider, answer = run_gateway(settings, handler)

    assert provider == provider_name
    assert answer.endswith("ответ")
    assert seen["url"] == expected_url
    if provider_name == "anthropic":
        assert seen["headers"]["authorization"] == "Bearer unit-test-token"
        assert seen["headers"]["anthropic-version"] == "2026-10-21"
        assert seen["body"]["model"] == "claude-sonnet-5-5"
        assert seen["body"]["max_tokens"] == settings.max_output_tokens
    elif provider_name == "gemini":
        assert seen["headers"]["x-goog-api-key"] == "unit-test-token"
        assert seen["body"]["systemInstruction"]["parts"][0]["text"]
        assert seen["body"]["contents"][0]["role"] == "user"
    elif provider_name == "xai":
        assert seen["headers"]["authorization"] == "Bearer unit-test-token"
        assert seen["body"]["model"] == "grok-4.7"
        assert seen["body"]["messages"][0]["role"] == "system"
    elif provider_name == "openrouter":
        assert seen["headers"]["authorization"] == "Bearer unit-test-token"
        assert seen["body"]["model"] == "openrouter/free"
        assert seen["headers"]["x-title"] == "Glitch AI Bridge"
        assert seen["body"]["messages"][0]["role"] == "system"
    elif provider_name == "groq":
        assert seen["headers"]["authorization"] == "Bearer unit-test-token"
        assert seen["body"]["model"] == "qwen/qwen3.8-27b"
    elif provider_name == "deepseek":
        assert seen["headers"]["authorization"] == "Bearer unit-test-token"
        assert seen["body"]["model"] == "deepseek-flash"
    elif provider_name == "mistral":
        assert seen["headers"]["authorization"] == "Bearer unit-test-token"
        assert seen["body"]["model"] == "mistral-large-latest"
    elif provider_name == "cloudflare":
        assert seen["headers"]["authorization"] == "Bearer unit-test-token"
        assert seen["body"]["model"] == "@cf/zai-org/glm-4.7-flash"
    elif provider_name == "nvidia":
        assert seen["headers"]["authorization"] == "Bearer unit-test-token"
        assert seen["body"]["model"] == "deepseek-ai/deepseek-v4-flash"
    elif provider_name == "cohere":
        assert seen["headers"]["authorization"] == "Bearer unit-test-token"
        assert seen["headers"]["x-client-name"] == "Glitch AI Bridge"
        assert seen["body"]["model"] == "command-a-plus-05-2026"
    else:
        assert seen["headers"]["authorization"] == "Bearer unit-test-token"
        assert seen["body"]["model"] == "sensenova-6.8-flash-lite"



def test_default_provider_prefers_openrouter_when_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AI_DEFAULT_PROVIDER", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "router-token")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-token")
    settings = Settings.from_env()
    assert settings.default_provider == "openrouter"


def test_billable_provider_requires_explicit_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AI_DEFAULT_PROVIDER", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "openai-token")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "claude-token")
    with pytest.raises(ValueError, match="AI_DEFAULT_PROVIDER explicitly"):
        Settings.from_env()


def test_explicit_default_provider_is_respected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AI_DEFAULT_PROVIDER", "anthropic")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-token")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "claude-token")
    settings = Settings.from_env()
    assert settings.default_provider == "anthropic"


def test_cloudflare_is_not_available_without_account_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "unit-test-token")
    monkeypatch.delenv("CLOUDFLARE_ACCOUNT_ID", raising=False)
    monkeypatch.delenv("AI_DEFAULT_PROVIDER", raising=False)
    settings = Settings.from_env()
    assert "cloudflare" not in settings.available_providers()


def test_cohere_text_response_parser() -> None:
    answer = ProviderGateway._cohere_text({
        "message": {
            "content": [
                {"type": "text", "text": "first"},
                {"type": "tool_call", "name": "unused", "parameters": {}},
                {"type": "text", "text": "second"},
            ]
        }
    })
    assert answer == "first\nsecond"


def test_cloudflare_default_model_is_current() -> None:
    assert DEFAULT_MODELS["cloudflare"] == "@cf/zai-org/glm-4.7-flash"


def test_sensenova_base_url_rejects_untrusted_hosts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SENSENOVA_API_KEY", "unit-test-token")
    monkeypatch.setenv("SENSENOVA_BASE_URL", "https://attacker.example/v1")
    monkeypatch.setenv("AI_DEFAULT_PROVIDER", "sensenova")
    with pytest.raises(ValueError, match="SENSENOVA_BASE_URL"):
        Settings.from_env()


def test_sensenova_mainland_region_url_is_allowed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SENSENOVA_API_KEY", "unit-test-token")
    monkeypatch.setenv("SENSENOVA_BASE_URL", "https://token.sensenova.cn/v1")
    monkeypatch.setenv("AI_DEFAULT_PROVIDER", "sensenova")
    settings = Settings.from_env()
    assert settings.sensenova_base_url == "https://token.sensenova.cn/v1"
    assert "sensenova" in settings.available_providers()
