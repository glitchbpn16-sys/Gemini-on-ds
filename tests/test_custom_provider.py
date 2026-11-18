from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
import pytest

from app.config import Settings
from app.providers import ProviderGateway


def run_gateway(settings: Settings, handler: Any) -> tuple[str, str, dict[str, Any]]:
    seen: dict[str, Any] = {}

    async def execute() -> tuple[str, str]:
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        gateway = ProviderGateway(settings, client=client)
        try:
            return await gateway.complete(
                [{"role": "user", "content": "Привет"}]
            )
        finally:
            await client.aclose()

    provider, answer = asyncio.run(execute())
    return provider, answer, seen


def test_custom_openai_compatible_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AI_DEFAULT_PROVIDER", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("CUSTOM_OPENAI_BASE_URL", "http://127.0.0.1:11434/v1")
    monkeypatch.setenv("CUSTOM_OPENAI_MODEL", "qwen-local")
    monkeypatch.setenv("CUSTOM_OPENAI_API_KEY", "local-test-token")
    settings = Settings.from_env()

    seen: dict[str, Any] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["authorization"] = request.headers.get("Authorization")
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "Локальный ответ"}}]},
        )

    provider, answer, _ = run_gateway_with_seen(settings, handler, seen)

    assert provider == "custom"
    assert answer == "Локальный ответ"
    assert seen["url"] == "http://127.0.0.1:11434/v1/chat/completions"
    assert seen["authorization"] == "Bearer local-test-token"
    assert seen["body"]["model"] == "qwen-local"


def run_gateway_with_seen(
    settings: Settings,
    handler: Any,
    seen: dict[str, Any],
) -> tuple[str, str, dict[str, Any]]:
    async def execute() -> tuple[str, str]:
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        gateway = ProviderGateway(settings, client=client)
        try:
            return await gateway.complete(
                [{"role": "user", "content": "Привет"}]
            )
        finally:
            await client.aclose()

    provider, answer = asyncio.run(execute())
    return provider, answer, seen


def test_custom_provider_requires_https_for_remote_hosts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CUSTOM_OPENAI_BASE_URL", "http://api.example.test/v1")
    monkeypatch.delenv("CUSTOM_OPENAI_ALLOW_INSECURE_HTTP", raising=False)

    with pytest.raises(ValueError, match="HTTPS"):
        Settings.from_env()
