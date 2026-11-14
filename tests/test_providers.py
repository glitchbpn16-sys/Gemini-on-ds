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
    }
    for env_name in names.values():
        monkeypatch.delenv(env_name, raising=False)
    monkeypatch.setenv(names[provider], "unit-test-token")
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
        "anthropic": "claude-sonnet-5",
        "gemini": "gemini-3.8-flash",
        "xai": "grok-4.7",
        "openrouter": "openrouter/free",
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
    else:
        assert seen["headers"]["authorization"] == "Bearer unit-test-token"
        assert seen["body"]["model"] == "openrouter/free"
        assert seen["headers"]["x-title"] == "Glitch AI Bridge"
        assert seen["body"]["messages"][0]["role"] == "system"
