"""Lightweight session history service."""

from __future__ import annotations

from collections import defaultdict


class SessionService:
    def __init__(self) -> None:
        self._history: dict[str, list[dict]] = defaultdict(list)

    async def get_history(self, session_id: str) -> list[dict]:
        return list(self._history.get(session_id, []))

    async def save_turn(self, session_id: str, role: str, content: str) -> None:
        self._history[session_id].append({"role": role, "content": content})

    async def close(self) -> None:
        self._history.clear()


_service: SessionService | None = None


def get_session_service() -> SessionService:
    global _service
    if _service is None:
        _service = SessionService()
    return _service
