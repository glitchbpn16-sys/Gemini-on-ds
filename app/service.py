from __future__ import annotations

from app.config import Settings
from app.memory import ConversationMemory, RateLimiter
from app.providers import ProviderGateway


class ChatService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.gateway = ProviderGateway(settings)
        # Keep only a modest short-lived context window in RAM.
        self.memory = ConversationMemory(max_messages=12)
        self.limiter = RateLimiter(
            limit=settings.requests_per_minute,
            window_seconds=60,
        )

    def available_providers(self) -> list[str]:
        return self.gateway.available()

    def clear(self, conversation_id: str) -> None:
        self.memory.clear(conversation_id)

    async def ask(
        self,
        conversation_id: str,
        prompt: str,
        preferred_provider: str | None = None,
    ) -> tuple[str, str]:
        prompt = prompt.strip()
        if not prompt:
            raise ValueError("Сообщение пустое.")
        if len(prompt) > self.settings.max_prompt_chars:
            raise ValueError(
                f"Сообщение слишком длинное. Лимит: {self.settings.max_prompt_chars} символов."
            )
        if not self.limiter.allow(conversation_id):
            raise ValueError("Слишком часто. Подожди минуту и попробуй снова.")

        messages = self.memory.history(conversation_id)
        messages.append({"role": "user", "content": prompt})
        provider, answer = await self.gateway.complete(messages, preferred_provider)
        self.memory.add_exchange(conversation_id, prompt, answer)
        return provider, answer
