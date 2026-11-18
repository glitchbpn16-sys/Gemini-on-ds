from __future__ import annotations

import hmac
import secrets
from typing import Annotated

from mcp.server import MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field
from starlette.responses import Response

from app.service import ChatService


class BearerAuthMiddleware:
    """Protect every MCP HTTP request with a constant-time Bearer check."""

    def __init__(self, app, access_token: str) -> None:
        if not access_token:
            raise ValueError("MCP access token must not be empty")
        self.app = app
        self.expected = f"Bearer {access_token}"

    async def __call__(self, scope, receive, send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        headers = {
            key.lower(): value.decode("latin-1")
            for key, value in scope.get("headers", [])
        }
        supplied = headers.get(b"authorization", "")
        if not hmac.compare_digest(supplied, self.expected):
            response = Response(
                content="Unauthorized",
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)


def create_mcp_app(service: ChatService, access_token: str):
    """Create an MCP Streamable HTTP server with a deliberately small toolset."""
    if not access_token:
        raise ValueError("MCP_API_TOKEN is required when MCP is enabled")

    server = MCPServer("Glitch AI Bridge")

    @server.tool(
        annotations=ToolAnnotations(
            read_only_hint=True,
            open_world_hint=False,
        )
    )
    def list_ai_providers() -> list[str]:
        """List AI providers configured by the server owner."""
        return service.available_providers()

    @server.tool()
    async def ask_ai(
        message: Annotated[
            str,
            Field(min_length=1, max_length=8000, description="Message to send to the selected AI provider."),
        ],
        provider: Annotated[
            str | None,
            Field(default=None, max_length=40, description="Optional configured provider name."),
        ] = None,
    ) -> str:
        """Send one request to a configured AI provider; no shell or device-control tools are exposed."""
        conversation_id = f"mcp:{secrets.token_urlsafe(18)}"
        try:
            selected, answer = await service.ask(
                conversation_id,
                message,
                provider,
            )
            return f"[{selected}] {answer}"
        finally:
            # MCP calls are isolated; they do not share or persist chat history.
            service.clear(conversation_id)

    app = server.streamable_http_app()
    return BearerAuthMiddleware(app, access_token)
