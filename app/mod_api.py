from __future__ import annotations

import hmac

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from app.service import ChatService


class ModMessage(BaseModel):
    server_id: str = Field(min_length=1, max_length=120)
    room_id: str = Field(min_length=1, max_length=120)
    user_id: str = Field(min_length=1, max_length=120)
    message: str = Field(min_length=1, max_length=8000)
    provider: str | None = Field(default=None, max_length=40)


def create_mod_app(service: ChatService, access_token: str | None) -> FastAPI:
    app = FastAPI(
        title="Glitch AI Mod Bridge",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/v1/mods/message")
    async def mod_message(
        payload: ModMessage,
        authorization: str | None = Header(default=None),
    ) -> dict[str, str]:
        if not access_token:
            raise HTTPException(status_code=503, detail="Mod API is not configured")
        supplied = authorization or ""
        expected = f"Bearer {access_token}"
        if not hmac.compare_digest(supplied, expected):
            raise HTTPException(status_code=401, detail="Unauthorized")
        conversation_id = (
            f"mod:{payload.server_id}:{payload.room_id}:{payload.user_id}"
        )
        try:
            provider, answer = await service.ask(
                conversation_id, payload.message, payload.provider
            )
        except ValueError as exc:
            raise HTTPException(status_code=429, detail=str(exc)) from None
        except RuntimeError:
            raise HTTPException(status_code=502, detail="AI provider request failed") from None
        return {"provider": provider, "reply": answer}

    return app
