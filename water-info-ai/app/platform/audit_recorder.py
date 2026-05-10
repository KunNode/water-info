"""Audit recorder with graceful degradation."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from pydantic import BaseModel

from app.platform.audit_models import (
    AgentRunRecord,
    DecisionLogRecord,
    EvidenceTraceRecord,
    SkillRunRecord,
    ToolCallRecord,
)

logger = logging.getLogger(__name__)


class AuditRecorder:
    def __init__(self, platform_client: Any, enabled: bool = True, buffer_limit: int = 100):
        self._client = platform_client
        self._enabled = enabled
        self._buffer_limit = buffer_limit
        self._disabled_due_to_missing_tables = False
        self.buffer: list[tuple[str, dict]] = []

    async def record_agent_run(self, run: AgentRunRecord) -> None:
        await self._record("ai_agent_run", run)

    async def record_tool_call(self, call: ToolCallRecord) -> None:
        await self._record("ai_tool_call", call)

    async def record_evidence_trace(self, trace: EvidenceTraceRecord) -> None:
        await self._record("ai_evidence_trace", trace)

    async def record_decision(self, decision: DecisionLogRecord) -> None:
        await self._record("ai_decision_log", decision)

    async def record_skill_run(self, run: SkillRunRecord) -> None:
        await self._record("ai_skill_run", run)

    async def _record(self, table: str, record: BaseModel) -> None:
        if not self._enabled or self._disabled_due_to_missing_tables:
            return
        payload = record.model_dump(mode="json")
        try:
            if hasattr(self._client, "post_audit_record"):
                await self._client.post_audit_record(table, payload)
            else:
                await self._client.post(f"/api/v1/ai-audit/{table}", json=payload)
        except Exception as exc:
            message = str(exc).lower()
            if "missing table" in message or "does not exist" in message or "404" in message:
                logger.warning("audit tables unavailable; buffering audit record and disabling further writes: %s", exc)
                self._disabled_due_to_missing_tables = True
            else:
                logger.warning("audit record failed; buffering for retry: %s", exc)
            self._buffer(table, payload)

    def _buffer(self, table: str, payload: dict) -> None:
        self.buffer.append((table, payload))
        if len(self.buffer) > self._buffer_limit:
            self.buffer = self.buffer[-self._buffer_limit:]

    async def retry_buffered(self) -> None:
        if not self._enabled or self._disabled_due_to_missing_tables:
            return
        pending = list(self.buffer)
        self.buffer.clear()
        for table, payload in pending:
            try:
                if hasattr(self._client, "post_audit_record"):
                    await self._client.post_audit_record(table, payload)
                else:
                    await self._client.post(f"/api/v1/ai-audit/{table}", json=payload)
            except Exception:
                self._buffer(table, payload)
                await asyncio.sleep(0)


_audit_recorder: AuditRecorder | None = None


def set_audit_recorder(recorder: AuditRecorder) -> None:
    global _audit_recorder
    _audit_recorder = recorder


def get_audit_recorder() -> AuditRecorder | None:
    return _audit_recorder
