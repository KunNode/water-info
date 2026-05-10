"""Application-level memory orchestration for the flood assistant."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.config import get_settings
from app.database import get_db_service
from app.memory.models import MemoryCandidate, MemoryContext, MemorySearchResult, MemoryType
from app.rag.embedder import get_embedding_client
from app.services.llm import get_llm
from app.state import RiskAssessment, to_plain_data
from app.utils.json_parser import extract_json

logger = logging.getLogger(__name__)


def _clamp(value: Any, default: float = 0.5) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except Exception:
        return default


def build_memory_namespaces(user_id: str = "", session_id: str = "") -> list[str]:
    """Return read namespaces ordered from most personal to shared context."""
    namespaces: list[str] = []
    if user_id:
        namespaces.append(f"user:{user_id}:flood_assistant")
    elif session_id:
        namespaces.append(f"anonymous_session:{session_id}:flood_assistant")
    namespaces.append("global:flood_ops")
    return namespaces


def build_write_namespace(user_id: str = "", session_id: str = "") -> str:
    if user_id:
        return f"user:{user_id}:flood_assistant"
    return f"anonymous_session:{session_id}:flood_assistant"


def to_store_namespace(namespace: str) -> tuple[str, ...]:
    return tuple(part for part in namespace.split(":") if part)


def _normalize_chat_messages(rows: list[dict], *, limit: int = 10) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    for row in rows:
        role = str(row.get("role") or "")
        content = str(row.get("content") or "").strip()
        status = str(row.get("status") or "completed")
        if role not in {"user", "assistant"} or not content or status in {"failed", "streaming"}:
            continue
        messages.append({"role": role, "content": content[:1000]})
    return messages[-limit:]


def _normalize_snapshot(row: dict[str, Any]) -> dict[str, Any]:
    """Convert a raw conversation_snapshot row into a JSON-safe prompt payload.

    asyncpg returns `updated_at` as a `datetime` and the JSONB columns may
    arrive as serialised strings depending on the driver. Callers downstream
    (supervisor, conversation_assistant, etc.) embed this dict into
    ``json.dumps`` payloads, so keep everything primitive here.
    """
    def _decode_json(value: Any) -> Any:
        if isinstance(value, str):
            try:
                return json.loads(value)
            except Exception:
                return value
        return value

    updated_at = row.get("updated_at")
    return {
        "session_id": str(row.get("session_id") or ""),
        "risk_level": str(row.get("risk_level") or "none"),
        "plan_info": _decode_json(row.get("plan_info")) or {},
        "agent_status_summary": _decode_json(row.get("agent_status_summary")) or {},
        "query_count": int(row.get("query_count") or 0),
        "updated_at": updated_at.isoformat() if hasattr(updated_at, "isoformat") else (str(updated_at) if updated_at else None),
    }


class MemoryService:
    """Loads concise memory context and writes high-value memories after turns."""

    def __init__(self) -> None:
        self._settings = get_settings()

    async def load_context(
        self,
        *,
        user_id: str = "",
        session_id: str,
        query: str,
        recent_messages: list[dict[str, str]] | None = None,
        store=None,
    ) -> MemoryContext:
        db = get_db_service()
        summary = ""
        snapshot: dict[str, Any] | None = None
        memories: list[MemorySearchResult] = []

        try:
            latest_summary = await db.get_latest_conversation_summary(session_id)
            if latest_summary:
                summary = str(latest_summary.get("summary") or "")
        except Exception as exc:
            logger.debug("[%s] memory summary load skipped: %s", session_id, exc)

        try:
            raw_snapshot = await db.get_conversation_snapshot(session_id)
            snapshot = _normalize_snapshot(raw_snapshot) if raw_snapshot else None
        except Exception as exc:
            logger.debug("[%s] memory snapshot load skipped: %s", session_id, exc)

        recent_session_messages = recent_messages or []
        if len(recent_session_messages) <= 1 and hasattr(db, "get_conversation_messages"):
            try:
                db_messages = _normalize_chat_messages(
                    await db.get_conversation_messages(session_id, limit=10),
                    limit=10,
                )
                if db_messages:
                    recent_session_messages = db_messages
            except Exception as exc:
                logger.debug("[%s] recent conversation messages load skipped: %s", session_id, exc)

        embedding: list[float] | None = None
        embedder = get_embedding_client()
        if embedder.is_enabled and query.strip():
            try:
                vectors = await embedder.embed_texts([query])
                embedding = vectors[0] if vectors else None
            except Exception as exc:
                logger.debug("[%s] memory embedding search skipped: %s", session_id, exc)

        try:
            rows = await db.search_memory_items(
                namespaces=build_memory_namespaces(user_id, session_id),
                query=query,
                embedding=embedding,
                top_n=6,
            )
            memories = [
                MemorySearchResult(
                    id=row.get("id"),
                    namespace=str(row.get("namespace") or ""),
                    item_type=str(row.get("item_type") or MemoryType.FACT.value),
                    content=str(row.get("content") or ""),
                    importance=float(row.get("importance") or 0.5),
                    confidence=float(row.get("confidence") or 0.5),
                    score=float(row["score"]) if row.get("score") is not None else None,
                    metadata=row.get("metadata") or {},
                    source_session_id=str(row.get("source_session_id") or ""),
                    updated_at=str(row.get("updated_at")) if row.get("updated_at") else None,
                )
                for row in rows
                if row.get("content")
            ]
        except Exception as exc:
            logger.debug("[%s] memory search skipped: %s", session_id, exc)

        if store is not None:
            memories.extend(await self._load_store_memories(store, user_id=user_id, session_id=session_id, query=query))
            memories = self._dedupe_results(memories)

        return MemoryContext(
            summary=summary,
            recent_messages=recent_session_messages,
            memories=memories,
            snapshot=snapshot,
        )

    async def write_from_state(self, state: dict, *, store=None) -> dict[str, Any]:
        session_id = str(state.get("session_id") or "")
        if not session_id:
            return {"saved": 0, "skipped": "missing_session_id"}

        candidates = await self.extract_candidates(state)
        if not candidates:
            await self.summarize_session_if_needed(session_id)
            return {"saved": 0, "skipped": "no_candidates"}

        namespace = build_write_namespace(str(state.get("user_id") or ""), session_id)
        texts = [candidate.content for candidate in candidates]
        embeddings: list[list[float]] = []
        embedder = get_embedding_client()
        if embedder.is_enabled:
            try:
                embeddings = await embedder.embed_texts(texts)
            except Exception as exc:
                logger.debug("[%s] memory write embeddings skipped: %s", session_id, exc)

        saved = 0
        saved_items: list[dict[str, Any]] = []
        db = get_db_service()
        for index, candidate in enumerate(candidates):
            if not candidate.content.strip() or candidate.importance < 0.35:
                continue
            embedding = embeddings[index] if index < len(embeddings) else None
            try:
                memory_id = await db.upsert_memory_item(
                    namespace=namespace,
                    session_id=session_id,
                    source_session_id=session_id,
                    item_type=candidate.item_type.value,
                    content=candidate.content.strip(),
                    importance=candidate.importance,
                    confidence=candidate.confidence,
                    metadata=candidate.metadata,
                    embedding=embedding,
                    embedding_model=self._settings.embedding_model if embedding else "",
                )
                saved_items.append({
                    "id": memory_id,
                    "namespace": namespace,
                    "item_type": candidate.item_type.value,
                    "content": candidate.content.strip(),
                    "importance": candidate.importance,
                    "confidence": candidate.confidence,
                    "metadata": candidate.metadata,
                    "source_session_id": session_id,
                })
                saved += 1
            except Exception as exc:
                logger.debug("[%s] memory save skipped: %s", session_id, exc)

        if store is not None and saved_items:
            await self._mirror_to_store(store, saved_items)

        await self.summarize_session_if_needed(session_id)
        return {"saved": saved, "candidate_count": len(candidates), "namespace": namespace, "store_saved": bool(store and saved_items)}

    async def extract_candidates(self, state: dict) -> list[MemoryCandidate]:
        query = str(state.get("user_query") or "")
        if any(marker in query for marker in ("不用长期记住", "不要长期记住", "只在当前会话", "仅当前会话")):
            return []

        candidates = self._deterministic_candidates(state)
        if any(candidate.metadata.get("reason") == "user_explicit_memory_request" for candidate in candidates):
            return self._dedupe_candidates(candidates)

        llm = get_llm()
        if not llm.is_enabled:
            return candidates

        try:
            response = await llm.ainvoke(
                json.dumps(
                    {
                        "user_query": state.get("user_query", ""),
                        "final_response": state.get("final_response", ""),
                        "risk_assessment": to_plain_data(state.get("risk_assessment")),
                        "emergency_plan": to_plain_data(state.get("emergency_plan")),
                        "existing_memory_context": state.get("memory_context", {}),
                    },
                    ensure_ascii=False,
                ),
                system_prompt=(
                    "你是防汛助手的记忆筛选器。只提取未来对同一用户或防汛业务有稳定价值的信息。"
                    "不要保存临时寒暄、一次性查询、敏感凭据、原始联系方式。"
                    "只返回 JSON："
                    '{"memories":[{"type":"fact|preference|decision|operation|todo",'
                    '"content":"可独立理解的一句话","importance":0到1,"confidence":0到1,'
                    '"metadata":{"reason":"保存原因"}}]}'
                ),
                temperature=0.0,
                response_format={"type": "json_object"},
            )
            parsed = extract_json(getattr(response, "content", None)) or {}
            for item in parsed.get("memories") or []:
                content = str(item.get("content") or "").strip()
                if not content:
                    continue
                item_type = self._memory_type(str(item.get("type") or MemoryType.FACT.value))
                candidates.append(
                    MemoryCandidate(
                        item_type=item_type,
                        content=content[:1000],
                        importance=_clamp(item.get("importance"), 0.5),
                        confidence=_clamp(item.get("confidence"), 0.5),
                        metadata=item.get("metadata") if isinstance(item.get("metadata"), dict) else {},
                    )
                )
        except Exception as exc:
            logger.debug("[%s] memory extraction skipped: %s", state.get("session_id", ""), exc)

        return self._dedupe_candidates(candidates)

    async def summarize_session_if_needed(self, session_id: str, *, min_messages: int = 30) -> None:
        db = get_db_service()
        try:
            rows = await db.get_conversation_messages(session_id, limit=40)
        except Exception:
            return
        if len(rows) < min_messages:
            return

        start_id = int(rows[0].get("id") or 0)
        end_id = int(rows[-1].get("id") or 0)
        latest = await db.get_latest_conversation_summary(session_id)
        if latest and int(latest.get("end_turn") or 0) >= end_id:
            return

        summary = self._simple_summary(rows)
        llm = get_llm()
        if llm.is_enabled:
            try:
                response = await llm.ainvoke(
                    json.dumps(
                        {"messages": [{"role": row["role"], "content": row["content"]} for row in rows]},
                        ensure_ascii=False,
                    ),
                    system_prompt="把这段防汛助手会话压缩成不超过 300 字的上下文摘要，保留用户目标、站点、风险、预案和未完成事项。",
                    temperature=0.0,
                )
                content = getattr(response, "content", "").strip()
                if content:
                    summary = content[:1200]
            except Exception:
                pass

        await db.save_conversation_summary(session_id, summary, start_id, end_id)

    def _deterministic_candidates(self, state: dict) -> list[MemoryCandidate]:
        query = str(state.get("user_query") or "").strip()
        candidates: list[MemoryCandidate] = []
        for marker in ("请记住", "记住", "以后记得"):
            if marker in query:
                remembered = query.split(marker, 1)[1].strip(" ：:，,。")
                if remembered:
                    candidates.append(
                        MemoryCandidate(
                            item_type=MemoryType.PREFERENCE if "偏好" in remembered else MemoryType.FACT,
                            content=remembered[:1000],
                            importance=0.85,
                            confidence=0.9,
                            metadata={"reason": "user_explicit_memory_request"},
                        )
                    )
                    break

        assessment = state.get("risk_assessment")
        if isinstance(assessment, RiskAssessment) and assessment.risk_level.value not in {"none", "low"}:
            risks = "；".join(assessment.key_risks[:3])
            if risks:
                candidates.append(
                    MemoryCandidate(
                        item_type=MemoryType.OPERATION,
                        content=f"本次会话识别到 {assessment.risk_level.value} 风险：{risks}",
                        importance=0.65,
                        confidence=0.75,
                        metadata={"reason": "risk_assessment_memory"},
                    )
                )

        plan = state.get("emergency_plan")
        plan_name = getattr(plan, "plan_name", "") if plan else ""
        if plan_name:
            candidates.append(
                MemoryCandidate(
                    item_type=MemoryType.DECISION,
                    content=f"本次会话生成了防汛预案：{plan_name}",
                    importance=0.6,
                    confidence=0.75,
                    metadata={"reason": "plan_generation_memory", "plan_id": getattr(plan, "plan_id", "")},
                )
            )
        return candidates

    @staticmethod
    def _dedupe_candidates(candidates: list[MemoryCandidate]) -> list[MemoryCandidate]:
        seen: set[tuple[str, str]] = set()
        deduped: list[MemoryCandidate] = []
        for candidate in candidates:
            key = (candidate.item_type.value, candidate.content.strip())
            if key in seen:
                continue
            seen.add(key)
            deduped.append(candidate)
        return deduped[:8]

    async def _mirror_to_store(self, store, saved_items: list[dict[str, Any]]) -> None:
        for item in saved_items:
            try:
                namespace = to_store_namespace(str(item["namespace"]))
                await store.aput(
                    namespace,
                    str(item["id"]),
                    {
                        "type": item["item_type"],
                        "content": item["content"],
                        "importance": item["importance"],
                        "confidence": item["confidence"],
                        "metadata": item["metadata"],
                        "source_session_id": item["source_session_id"],
                    },
                )
            except Exception as exc:
                logger.debug("LangGraph store memory mirror skipped: %s", exc)

    async def _load_store_memories(self, store, *, user_id: str, session_id: str, query: str) -> list[MemorySearchResult]:
        results: list[MemorySearchResult] = []
        for namespace in build_memory_namespaces(user_id, session_id):
            try:
                items = await store.asearch(to_store_namespace(namespace), limit=6)
            except Exception as exc:
                logger.debug("LangGraph store memory search skipped: %s", exc)
                continue
            for item in items:
                value = getattr(item, "value", {}) or {}
                results.append(
                    MemorySearchResult(
                        id=None,
                        namespace=namespace,
                        item_type=str(value.get("type") or MemoryType.FACT.value),
                        content=str(value.get("content") or ""),
                        importance=float(value.get("importance") or 0.5),
                        confidence=float(value.get("confidence") or 0.5),
                        score=getattr(item, "score", None),
                        metadata=value.get("metadata") if isinstance(value.get("metadata"), dict) else {},
                        source_session_id=str(value.get("source_session_id") or ""),
                        updated_at=str(getattr(item, "updated_at", "")) or None,
                    )
                )
        return [item for item in results if item.content]

    @staticmethod
    def _dedupe_results(memories: list[MemorySearchResult]) -> list[MemorySearchResult]:
        seen: set[tuple[str, str]] = set()
        deduped: list[MemorySearchResult] = []
        for memory in sorted(memories, key=lambda item: item.importance, reverse=True):
            key = (memory.item_type, memory.content)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(memory)
        return deduped[:8]

    @staticmethod
    def _memory_type(value: str) -> MemoryType:
        try:
            return MemoryType(value)
        except ValueError:
            return MemoryType.FACT

    @staticmethod
    def _simple_summary(rows: list[dict[str, Any]]) -> str:
        snippets = []
        for row in rows[-12:]:
            role = row.get("role", "")
            content = str(row.get("content") or "").replace("\n", " ")
            snippets.append(f"{role}: {content[:120]}")
        return "；".join(snippets)[:1200]


_memory_service: MemoryService | None = None


def get_memory_service() -> MemoryService:
    global _memory_service
    if _memory_service is None:
        _memory_service = MemoryService()
    return _memory_service
