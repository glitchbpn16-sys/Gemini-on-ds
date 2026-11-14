from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from app.service import ChatService


def _chunks(text: str, limit: int = 1850) -> list[str]:
    result: list[str] = []
    while text:
        split_at = min(limit, len(text))
        if split_at < len(text):
            boundary = text.rfind("\n", 0, split_at)
            if boundary > limit // 2:
                split_at = boundary
        result.append(text[:split_at])
        text = text[split_at:].lstrip()
    return result or ["Пустой ответ."]


class GlitchDiscordBot(commands.Bot):
    async def setup_hook(self) -> None:
        await self.tree.sync()


class DiscordAdapter:
    def __init__(self, token: str, service: ChatService) -> None:
        self.token = token
        self.service = service
        self.providers_by_user: dict[int, str] = {}

        intents = discord.Intents.default()
        self.bot = GlitchDiscordBot(command_prefix="!", intents=intents)

        @self.bot.event
        async def on_ready() -> None:
            print(f"Discord adapter connected as {self.bot.user}")

        @self.bot.tree.command(name="ask", description="Задать вопрос Glitch AI")
        @app_commands.describe(question="Текст вопроса")
        async def ask(interaction: discord.Interaction, question: str) -> None:
            await interaction.response.defer(thinking=True)
            conversation_id = (
                f"discord:{interaction.guild_id or 'dm'}:"
                f"{interaction.channel_id}:{interaction.user.id}"
            )
            try:
                provider, answer = await self.service.ask(
                    conversation_id,
                    question,
                    self.providers_by_user.get(interaction.user.id),
                )
                parts = _chunks(f"Модель: {provider}\n\n{answer}")
                await interaction.followup.send(
                    parts[0], allowed_mentions=discord.AllowedMentions.none()
                )
                for part in parts[1:]:
                    await interaction.followup.send(
                        part, allowed_mentions=discord.AllowedMentions.none()
                    )
            except (ValueError, RuntimeError) as exc:
                await interaction.followup.send(str(exc), ephemeral=True)
            except Exception:
                await interaction.followup.send(
                    "Не удалось обработать запрос. Проверь настройки сервера.",
                    ephemeral=True,
                )

        @self.bot.tree.command(name="provider", description="Выбрать модельного провайдера")
        @app_commands.describe(name="openai, anthropic, gemini, xai или openrouter")
        async def provider(interaction: discord.Interaction, name: str) -> None:
            name = name.strip().lower()
            if name not in self.service.available_providers():
                choices = ", ".join(self.service.available_providers()) or "нет настроенных"
                await interaction.response.send_message(
                    f"Провайдер недоступен. Настроены: {choices}.",
                    ephemeral=True,
                )
                return
            self.providers_by_user[interaction.user.id] = name
            await interaction.response.send_message(
                f"Для тебя выбран провайдер {name}.",
                ephemeral=True,
            )

        @self.bot.tree.command(name="providers", description="Показать доступные провайдеры")
        async def providers(interaction: discord.Interaction) -> None:
            names = ", ".join(self.service.available_providers()) or "Пока нет настроенных API-ключей"
            await interaction.response.send_message(names, ephemeral=True)

        @self.bot.tree.command(name="clear", description="Очистить контекст текущего чата")
        async def clear(interaction: discord.Interaction) -> None:
            conversation_id = (
                f"discord:{interaction.guild_id or 'dm'}:"
                f"{interaction.channel_id}:{interaction.user.id}"
            )
            self.service.clear(conversation_id)
            self.providers_by_user.pop(interaction.user.id, None)
            await interaction.response.send_message(
                "Контекст очищен.", ephemeral=True
            )

        @self.bot.event
        async def on_error(event_method: str, *args: object, **kwargs: object) -> None:
            print(f"Discord event failed: {event_method}")

    async def run(self) -> None:
        try:
            await self.bot.start(self.token)
        finally:
            await self.bot.close()
