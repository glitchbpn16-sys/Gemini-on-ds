from app.memory import ConversationMemory, RateLimiter


def test_conversation_memory_keeps_only_recent_messages() -> None:
    memory = ConversationMemory(max_messages=4)
    for index in range(4):
        memory.add_exchange("chat", f"user-{index}", f"assistant-{index}")

    history = memory.history("chat")
    assert len(history) == 4
    assert history[0]["content"] == "user-2"
    assert history[-1]["content"] == "assistant-3"


def test_clear_removes_conversation() -> None:
    memory = ConversationMemory()
    memory.add_exchange("chat", "hello", "hi")
    memory.clear("chat")
    assert memory.history("chat") == []


def test_rate_limiter_rejects_excess_requests() -> None:
    limiter = RateLimiter(limit=2, window_seconds=60)
    assert limiter.allow("user")
    assert limiter.allow("user")
    assert not limiter.allow("user")
