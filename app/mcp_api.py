from __future__ import annotations

import contextlib
import hmac
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from mcp.server.mcpserver import MCPServer
from starlette.applications import Starlette
from starlette.responses import Response
from starlette.routing import Mount

from app.service import ChatService


class BearerAuthMiddleware:
    """Protect every MCP HTTP request with a constant-time Bearer check."""

    def __init__(self, app: Callable[..., Awaitable[None]], access_token: str) -> None:
        if not access_token:
            raise ValueError("MCP_API_TOKEN is required when MCP is enabled")
        self.app = app
        self.expected = f"Bearer {access_token}"

    async def __call__(self, scope: dict[str, Any], receive, send) -> None:
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
    """Create an authenticated, stateless Streamable HTTP MCP server."""
    if not access_token:
        raise ValueError("MCP_API_TOKEN is required when MCP is enabled")

    server = MCPServer("Glitch AI Bridge")

    @server.tool()
    def list_ai_providers() -> str:
        """List the AI providers configured by the server owner."""
        providers = service.available_providers()
        return ", ".join(providers) if providers else "No providers configured"

    @server.tool()
    async def ask_ai(message: str, provider: str = "") -> str:
        """Send a bounded request to a configured AI provider; no shell or device-control tools are exposed."""
        message = message.strip()
        if not message:
            raise ValueError("Message must not be empty")
        if len(message) > service.settings.max_prompt_chars:
            raise ValueError(
                f"Message exceeds the {service.settings.max_prompt_chars}-character limit"
            )
        # One shared limiter key prevents clients from evading quotas by creating
        # fresh conversation IDs. MCP calls are stateless and do not retain history.
        if not service.limiter.allow("mcp"):
            raise ValueError("MCP request limit reached; try again later")
        selected_provider, answer = await service.gateway.complete(
            [{"role": "user", "content": message}],
            provider.strip() or None,
        )
        return f"[{selected_provider}] {answer}"

    mcp_app = server.streamable_http_app(
        json_response=True,
        stateless_http=True,
        host=service.settings.mcp_host,
    )

    @contextlib.asynccontextmanager
    async def lifespan(_: Starlette) -> AsyncIterator[None]:
        async with server.session_manager.run():
            yield

    app = Starlette(
        routes=[Mount("/", app=mcp_app)],
        lifespan=lifespan,
    )
    return BearerAuthMiddleware(app, access_token)
