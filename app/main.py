from __future__ import annotations

import asyncio

import uvicorn

from app.config import Settings
from app.mod_api import create_mod_app
from app.platforms.discord_bot import DiscordAdapter
from app.platforms.telegram_bot import TelegramAdapter
from app.service import ChatService


async def main() -> None:
    settings = Settings.from_env()
    service = ChatService(settings)
    available = service.available_providers()
    if not available:
        raise SystemExit(
            "Не настроен ни один AI API. Добавь ключ или CUSTOM_OPENAI_BASE_URL "
            "в переменные окружения; см. .env.example."
        )

    if settings.default_provider not in available:
        print(
            f"Default provider '{settings.default_provider}' is not configured. "
            f"Available: {', '.join(available)}. Set AI_DEFAULT_PROVIDER."
        )

    tasks: list[asyncio.Task[object]] = []

    if settings.discord_token:
        tasks.append(
            asyncio.create_task(
                DiscordAdapter(settings.discord_token, service).run(),
                name="discord",
            )
        )
    if settings.telegram_token:
        tasks.append(
            asyncio.create_task(
                TelegramAdapter(settings.telegram_token, service).run(),
                name="telegram",
            )
        )
    if settings.mods_api_token:
        config = uvicorn.Config(
            create_mod_app(service, settings.mods_api_token),
            host=settings.host,
            port=settings.port,
            log_level="warning",
            access_log=False,
            limit_concurrency=16,
            timeout_keep_alive=5,
        )
        tasks.append(
            asyncio.create_task(uvicorn.Server(config).serve(), name="mods-api")
        )

    if settings.mcp_enabled and settings.mcp_api_token:
        from app.mcp_api import create_mcp_app

        config = uvicorn.Config(
            create_mcp_app(service, settings.mcp_api_token),
            host=settings.mcp_host,
            port=settings.mcp_port,
            log_level="warning",
            access_log=False,
            limit_concurrency=8,
            timeout_keep_alive=5,
        )
        tasks.append(
            asyncio.create_task(uvicorn.Server(config).serve(), name="mcp-connect")
        )

    if not tasks:
        await service.gateway.close()
        raise SystemExit(
            "Нет включённых платформ. Укажи Discord/Telegram token, MODS_API_TOKEN "
            "или включи MCP_ENABLED=true с отдельным MCP_API_TOKEN."
        )

    print(f"Glitch AI Bridge started. AI providers: {', '.join(available)}")
    try:
        await asyncio.gather(*tasks)
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await service.gateway.close()


if __name__ == "__main__":
    asyncio.run(main())
