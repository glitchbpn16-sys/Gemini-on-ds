from __future__ import annotations

import asyncio
import re

from telegram import Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app.service import ChatService

MAX_TELEGRAM_TEXT = 4000


def _split(text: str) -> list[str]:
    chunks: list[str] = []
    while text:
        index = min(MAX_TELEGRAM_TEXT, len(text))
        if index < len(text):
            newline = text.rfind("\n", 0, index)
            if newline > MAX_TELEGRAM_TEXT // 2:
                index = newline
        chunks.append(text[:index])
        text = text[index:].lstrip()
    return chunks or ["Пустой ответ."]


class TelegramAdapter:
    def __init__(self, token: str, service: ChatService) -> None:
        self.token = token
        self.service = service
        self.application: Application = ApplicationBuilder().token(token).build()

        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("ask", self.ask_command))
        self.application.add_handler(CommandHandler("provider", self.provider))
        self.application.add_handler(CommandHandler("providers", self.providers))
        self.application.add_handler(CommandHandler("clear", self.clear))
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.text_message)
        )

    @staticmethod
    def _conversation_id(update: Update) -> str:
        chat = update.effective_chat
        user = update.effective_user
        return f"telegram:{chat.id if chat else 'unknown'}:{user.id if user else 'unknown'}"

    async def _answer(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, prompt: str
    ) -> None:
        message = update.effective_message
        if message is None:
            return
        provider_preference = context.user_data.get("provider")
        try:
            provider, answer = await self.service.ask(
                self._conversation_id(update), prompt, provider_preference
            )
            for part in _split(f"Модель: {provider}\n\n{answer}"):
                await message.reply_text(part)
        except (ValueError, RuntimeError) as exc:
            await message.reply_text(str(exc))
        except Exception:
            await message.reply_text(
                "Не удалось обработать запрос. Проверь настройки сервера."
            )

    async def start(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if update.effective_message:
            await update.effective_message.reply_text(
                "Glitch AI Bridge готов. Напиши сообщение или используй /ask. "
                "Команды: /providers, /provider, /clear."
            )

    async def ask_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        prompt = " ".join(context.args).strip()
        if not prompt:
            if update.effective_message:
                await update.effective_message.reply_text("Пример: /ask объясни Kotlin Flow")
            return
        await self._answer(update, context, prompt)

    async def text_message(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        message = update.effective_message
        chat = update.effective_chat
        if message is None or not message.text:
            return
        prompt = message.text.strip()
        if chat and chat.type != "private":
            username = context.bot.username
            if not username or f"@{username.lower()}" not in prompt.lower():
                return
            prompt = re.sub(
                rf"@{re.escape(username)}\b", "", prompt, flags=re.IGNORECASE
            ).strip()
        await self._answer(update, context, prompt)

    async def provider(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        message = update.effective_message
        if message is None:
            return
        name = context.args[0].lower() if context.args else ""
        available = self.service.available_providers()
        if name not in available:
            choices = ", ".join(available) or "нет настроенных"
            await message.reply_text(
                f"Укажи доступного провайдера. Настроены: {choices}. "
                "Пример: /provider openrouter"
            )
            return
        context.user_data["provider"] = name
        await message.reply_text(f"Выбран провайдер: {name}.")

    async def providers(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        message = update.effective_message
        if message:
            names = ", ".join(self.service.available_providers())
            await message.reply_text(names or "Пока нет настроенных API-ключей.")

    async def clear(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        self.service.clear(self._conversation_id(update))
        context.user_data.pop("provider", None)
        if update.effective_message:
            await update.effective_message.reply_text("Контекст очищен.")

    async def run(self) -> None:
        await self.application.initialize()
        await self.application.start()
        if self.application.updater is None:
            raise RuntimeError("Telegram updater не инициализирован")
        await self.application.updater.start_polling()
        print("Telegram adapter polling started")
        try:
            await asyncio.Event().wait()
        finally:
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
