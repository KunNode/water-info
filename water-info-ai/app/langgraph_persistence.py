"""Lifecycle management for LangGraph's official Postgres persistence."""

from __future__ import annotations

import logging
from contextlib import AsyncExitStack
from urllib.parse import quote_plus

from app.config import get_settings

logger = logging.getLogger(__name__)


class LangGraphPostgresPersistence:
    """Owns AsyncPostgresSaver/Store context managers for the app lifetime."""

    def __init__(self) -> None:
        self._stack = AsyncExitStack()
        self.checkpointer = None
        self.store = None
        self.enabled = False

    async def start(self) -> bool:
        settings = get_settings()
        if not settings.langgraph_postgres_enabled:
            logger.info("LangGraph Postgres persistence disabled")
            return False

        try:
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
            from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
            from langgraph.store.postgres.aio import AsyncPostgresStore
        except Exception as exc:
            logger.warning("LangGraph Postgres persistence package unavailable: %s", exc)
            return False

        conn_string = _build_conn_string()
        try:
            self.checkpointer = await self._stack.enter_async_context(
                AsyncPostgresSaver.from_conn_string(
                    conn_string,
                    pipeline=False,
                    serde=JsonPlusSerializer(pickle_fallback=True),
                )
            )
            await self.checkpointer.setup()

            self.store = await self._stack.enter_async_context(
                AsyncPostgresStore.from_conn_string(conn_string, pipeline=False)
            )
            await self.store.setup()
        except Exception as exc:
            await self.aclose()
            logger.warning("LangGraph Postgres persistence init failed; falling back to stateless graph: %s", exc)
            return False

        self.enabled = True
        logger.info("LangGraph Postgres checkpointer/store ready")
        return True

    async def aclose(self) -> None:
        self.enabled = False
        self.checkpointer = None
        self.store = None
        await self._stack.aclose()
        self._stack = AsyncExitStack()


def _build_conn_string() -> str:
    settings = get_settings()
    user = quote_plus(settings.pg_user)
    password = quote_plus(settings.pg_password)
    database = quote_plus(settings.pg_database)
    host = settings.pg_host
    port = settings.pg_port
    return f"postgresql://{user}:{password}@{host}:{port}/{database}?sslmode=disable"


_persistence: LangGraphPostgresPersistence | None = None


def get_langgraph_persistence() -> LangGraphPostgresPersistence:
    global _persistence
    if _persistence is None:
        _persistence = LangGraphPostgresPersistence()
    return _persistence
