"""DB-backed session history service — replaces the former in-memory store."""

from __future__ import annotations

from app.database import get_db_service


class SessionService:
    async def get_history(self, session_id: str) -> list[dict]:
        """Return the last 20 messages (10 turns) for LangGraph context."""
        try:
            rows = await get_db_service().get_conversation_messages(session_id, limit=20)
            return [{"role": r["role"], "content": r["content"]} for r in rows]
        except Exception:
            return []

    async def save_turn(self, session_id: str, role: str, content: str) -> None:
        try:
            await get_db_service().save_conversation_message(session_id, role, content)
        except Exception:
            pass

    async def close(self) -> None:
        pass  # connection pool is managed by DatabaseService


_service: SessionService | None = None


def get_session_service() -> SessionService:
    global _service
    if _service is None:
        _service = SessionService()
    return _service
