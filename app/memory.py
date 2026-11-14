from __future__ import annotations

from collections import defaultdict, deque
from time import monotonic


class ConversationMemory:
    """Small in-process context store. Nothing is written to disk."""

    def __init__(self, max_messages: int = 20) -> None:
        self._max_messages = max(2, max_messages)
        self._items: dict[str, deque[dict[str, str]]] = defaultdict(
            lambda: deque(maxlen=self._max_messages)
        )

    def history(self, key: str) -> list[dict[str, str]]:
        return list(self._items[key])

    def add_exchange(self, key: str, user_text: str, assistant_text: str) -> None:
        history = self._items[key]
        history.append({"role": "user", "content": user_text})
        history.append({"role": "assistant", "content": assistant_text})

    def clear(self, key: str) -> None:
        self._items.pop(key, None)


class RateLimiter:
    """Per-user in-memory sliding-window rate limiter."""

    def __init__(self, limit: int = 8, window_seconds: int = 60) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = monotonic()
        events = self._events[key]
        while events and now - events[0] > self.window_seconds:
            events.popleft()
        if len(events) >= self.limit:
            return False
        events.append(now)
        return True
