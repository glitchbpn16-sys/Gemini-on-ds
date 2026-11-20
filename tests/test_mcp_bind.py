from __future__ import annotations

import pytest

from app.config import Settings


def test_mcp_enabled_defaults_to_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCP_ENABLED", "true")
    monkeypatch.setenv("MCP_API_TOKEN", "test-token")
    monkeypatch.delenv("MCP_HOST", raising=False)

    settings = Settings.from_env()

    assert settings.mcp_host == "127.0.0.1"


@pytest.mark.parametrize("host", ["0.0.0.0", "192.168.1.10", "::"])
def test_mcp_rejects_non_loopback_bind(
    monkeypatch: pytest.MonkeyPatch,
    host: str,
) -> None:
    monkeypatch.setenv("MCP_ENABLED", "true")
    monkeypatch.setenv("MCP_API_TOKEN", "test-token")
    monkeypatch.setenv("MCP_HOST", host)

    with pytest.raises(ValueError, match="HTTPS reverse proxy"):
        Settings.from_env()


def test_mcp_accepts_localhost_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCP_ENABLED", "true")
    monkeypatch.setenv("MCP_API_TOKEN", "test-token")
    monkeypatch.setenv("MCP_HOST", "localhost")

    settings = Settings.from_env()

    assert settings.mcp_host == "localhost"
