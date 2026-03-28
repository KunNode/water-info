"""Redis 会话管理服务

管理多轮对话历史，支持 TTL 自动过期和上下文轮数限制。
"""

from __future__ import annotations

import json
from typing import Any

from loguru import logger

from app.config import get_settings

# TTL 和最大轮数
SESSION_TTL_SECONDS = 3600  # 1 小时
MAX_TURNS = 10


class SessionService:
    """Redis 会话管理"""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._redis = None

    async def _get_redis(self):
        if self._redis is None:
            import redis.asyncio as aioredis
            self._redis = aioredis.from_url(
                self._settings.redis_url,
                password=self._settings.redis_password or None,
                decode_responses=True,
            )
        return self._redis

    def _key(self, session_id: str) -> str:
        return f"water_ai:session:{session_id}"

    async def get_history(self, session_id: str) -> list[dict[str, Any]]:
        """获取会话历史（最多 MAX_TURNS 轮）"""
        try:
            r = await self._get_redis()
            raw = await r.lrange(self._key(session_id), 0, -1)
            return [json.loads(item) for item in raw]
        except Exception as e:
            logger.debug(f"获取会话历史失败: {e}")
            return []

    async def save_turn(self, session_id: str, role: str, content: str) -> None:
        """保存一轮对话，超过 MAX_TURNS 则裁剪最旧的"""
        try:
            r = await self._get_redis()
            key = self._key(session_id)
            turn = json.dumps({"role": role, "content": content}, ensure_ascii=False)
            await r.rpush(key, turn)
            # 裁剪到最多 MAX_TURNS * 2 条记录（每轮 user+assistant = 2 条）
            await r.ltrim(key, -(MAX_TURNS * 2), -1)
            await r.expire(key, SESSION_TTL_SECONDS)
        except Exception as e:
            logger.debug(f"保存会话记录失败: {e}")

    async def close(self) -> None:
        if self._redis:
            await self._redis.close()
            logger.info("Redis 会话连接已关闭")


_service: SessionService | None = None


def get_session_service() -> SessionService:
    global _service
    if _service is None:
        _service = SessionService()
    return _service
