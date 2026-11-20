from __future__ import annotations

import asyncio
from typing import Any

import httpx

from app.config import Settings


class ProviderError(RuntimeError):
    pass


class ProviderGateway:
    """REST gateway for first-party and custom OpenAI-compatible APIs."""

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None):
        self.settings = settings
        self._owns_client = client is None
        timeout = httpx.Timeout(
            float(settings.request_timeout_seconds),
            connect=min(15.0, float(settings.request_timeout_seconds)),
        )
        self.client = client or httpx.AsyncClient(
            timeout=timeout,
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )
        # Keep concurrent requests bounded; no busy background polling is used.
        self._semaphore = asyncio.Semaphore(settings.max_concurrent_ai_requests)

    async def close(self) -> None:
        if self._owns_client:
            await self.client.aclose()

    def available(self) -> list[str]:
        return self.settings.available_providers()

    async def complete(
        self,
        messages: list[dict[str, str]],
        preferred_provider: str | None = None,
    ) -> tuple[str, str]:
        provider = (preferred_provider or self.settings.default_provider).lower()
        if provider not in {
            "openai",
            "anthropic",
            "gemini",
            "xai",
            "openrouter",
            "custom",
        }:
            raise ProviderError("Неизвестный провайдер. Используй /providers.")
        if provider not in self.available():
            raise ProviderError(
                f"Провайдер {provider} не настроен: проверь переменные окружения."
            )

        order = [provider]
        for fallback in self.settings.fallback_order:
            if fallback not in order and fallback in self.available():
                order.append(fallback)

        failures: list[str] = []
        async with self._semaphore:
            for candidate in order:
                try:
                    answer = await self._request(candidate, messages)
                    return candidate, answer
                except ProviderError as exc:
                    failures.append(f"{candidate}: {exc}")
                    if candidate == provider and not self.settings.fallback_order:
                        break

        raise ProviderError(
            "Не удалось получить ответ ни от одного настроенного провайдера. "
            + "; ".join(failures[:3])
        )

    async def _request(
        self, provider: str, messages: list[dict[str, str]]
    ) -> str:
        key = self.settings.api_key(provider)
        if not key and provider != "custom":
            raise ProviderError("ключ не настроен")

        try:
            if provider == "openai":
                data = await self._post(
                    "https://api.openai.com/v1/responses",
                    {"Authorization": f"Bearer {key}"},
                    {
                        "model": self.settings.model(provider),
                        "instructions": self.settings.system_prompt,
                        "input": [
                            {"role": item["role"], "content": item["content"]}
                            for item in messages
                        ],
                        "max_output_tokens": self.settings.max_output_tokens,
                    },
                )
                answer = self._response_output_text(data)
            elif provider == "anthropic":
                data = await self._post(
                    "https://api.anthropic.com/v1/messages",
                    {
                        "Authorization": f"Bearer {key}",
                        "anthropic-version": "2026-10-21",
                    },
                    {
                        "model": self.settings.model(provider),
                        "system": self.settings.system_prompt,
                        "messages": messages,
                        "max_tokens": self.settings.max_output_tokens,
                    },
                )
                answer = self._content_blocks_text(data)
            elif provider == "gemini":
                contents = [
                    {
                        "role": "model" if item["role"] == "assistant" else "user",
                        "parts": [{"text": item["content"]}],
                    }
                    for item in messages
                ]
                data = await self._post(
                    "https://generativelanguage.googleapis.com/v1beta/models/"
                    f"{self.settings.model(provider)}:generateContent",
                    {"x-goog-api-key": key or ""},
                    {
                        "systemInstruction": {
                            "parts": [{"text": self.settings.system_prompt}]
                        },
                        "contents": contents,
                        "generationConfig": {
                            "maxOutputTokens": self.settings.max_output_tokens
                        },
                    },
                )
                answer = self._gemini_text(data)
            elif provider == "custom":
                base_url = self.settings.custom_openai_base_url
                if not base_url:
                    raise ProviderError("CUSTOM_OPENAI_BASE_URL is not configured")
                headers = {"Authorization": f"Bearer {key}"} if key else {}
                data = await self._post(
                    f"{base_url}/chat/completions",
                    headers,
                    {
                        "model": self.settings.model(provider),
                        "messages": [
                            {"role": "system", "content": self.settings.system_prompt},
                            *messages,
                        ],
                        "max_tokens": self.settings.max_output_tokens,
                    },
                )
                answer = self._chat_completion_text(data)
            else:
                base = (
                    "https://api.x.ai/v1/chat/completions"
                    if provider == "xai"
                    else "https://openrouter.ai/api/v1/chat/completions"
                )
                headers = {"Authorization": f"Bearer {key}"}
                if provider == "openrouter":
                    if self.settings.openrouter_site_url:
                        headers["HTTP-Referer"] = self.settings.openrouter_site_url
                    headers["X-Title"] = self.settings.openrouter_app_name
                data = await self._post(
                    base,
                    headers,
                    {
                        "model": self.settings.model(provider),
                        "messages": [
                            {"role": "system", "content": self.settings.system_prompt},
                            *messages,
                        ],
                        "max_tokens": self.settings.max_output_tokens,
                    },
                )
                answer = self._chat_completion_text(data)

            if not answer.strip():
                raise ProviderError("провайдер вернул пустой ответ")
            return answer.strip()
        except ProviderError:
            raise
        except (httpx.TimeoutException, httpx.NetworkError):
            raise ProviderError("ошибка сети или превышено время ожидания") from None
        except (KeyError, IndexError, TypeError, ValueError):
            raise ProviderError("неожиданный формат ответа API") from None

    async def _post(
        self, url: str, headers: dict[str, str], payload: dict[str, Any]
    ) -> dict[str, Any]:
        response = await self.client.post(url, headers=headers, json=payload)
        if response.status_code >= 400:
            # Do not include request headers or response bodies in logs/errors.
            raise ProviderError(
                f"HTTP {response.status_code}; проверь ключ, модель и лимиты"
            )
        try:
            result = response.json()
        except ValueError:
            raise ProviderError("API вернул некорректный JSON") from None
        if not isinstance(result, dict):
            raise ProviderError("API вернул неожиданный тип данных")
        return result

    @staticmethod
    def _response_output_text(data: dict[str, Any]) -> str:
        pieces: list[str] = []
        for item in data.get("output", []):
            if not isinstance(item, dict):
                continue
            for block in item.get("content", []):
                if isinstance(block, dict) and block.get("type") in {
                    "output_text",
                    "text",
                }:
                    text = block.get("text")
                    if isinstance(text, str):
                        pieces.append(text)
        return "\n".join(pieces)

    @staticmethod
    def _content_blocks_text(data: dict[str, Any]) -> str:
        return "\n".join(
            block["text"]
            for block in data.get("content", [])
            if isinstance(block, dict) and isinstance(block.get("text"), str)
        )

    @staticmethod
    def _gemini_text(data: dict[str, Any]) -> str:
        candidates = data.get("candidates", [])
        if not candidates:
            raise ProviderError("Gemini не вернул кандидатов ответа")
        parts = candidates[0].get("content", {}).get("parts", [])
        return "\n".join(
            part["text"]
            for part in parts
            if isinstance(part, dict) and isinstance(part.get("text"), str)
        )

    @staticmethod
    def _chat_completion_text(data: dict[str, Any]) -> str:
        choices = data.get("choices", [])
        if not choices:
            raise ProviderError("чатовый API не вернул choices")
        content = choices[0].get("message", {}).get("content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "\n".join(
                item.get("text", "")
                for item in content
                if isinstance(item, dict) and isinstance(item.get("text"), str)
            )
        raise ProviderError("неподдерживаемый формат message.content")
