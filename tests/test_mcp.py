from __future__ import annotations

from starlette.testclient import TestClient

from app.mcp_api import create_mcp_app


class DummyService:
    def available_providers(self) -> list[str]:
        return ["openrouter"]

    async def ask(self, conversation_id: str, prompt: str, preferred_provider: str | None = None):
        return preferred_provider or "openrouter", "test answer"

    def clear(self, conversation_id: str) -> None:
        return None


def test_mcp_endpoint_requires_bearer_token() -> None:
    app = create_mcp_app(DummyService(), "test-token")

    with TestClient(app) as client:
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_mcp_server_rejects_empty_token() -> None:
    try:
        create_mcp_app(DummyService(), "")
    except ValueError as exc:
        assert "MCP_API_TOKEN" in str(exc)
    else:
        raise AssertionError("An empty MCP token must be rejected")
