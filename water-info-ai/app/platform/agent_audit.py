"""Audit wrapper for LangGraph agent nodes."""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from app.config import get_settings
from app.platform.audit_models import (
    AgentRunRecord,
    DecisionLogRecord,
    EvidenceTraceRecord,
    SkillRunRecord,
    ToolCallRecord,
)
from app.platform.audit_recorder import get_audit_recorder
from app.platform.output_validator import validate_agent_output
from app.state import to_plain_data

AgentNode = Callable[[dict], Awaitable[dict]]


def audited_agent(agent_name: str, node: AgentNode) -> AgentNode:
    async def wrapped(state: dict) -> dict:
        settings = get_settings()
        recorder = get_audit_recorder()
        if not settings.audit_tables_enabled or recorder is None:
            update = await node(state)
            return await _maybe_attach_validation(agent_name, update, settings.structured_output_enabled)

        agent_run_id = str(state.get("agent_run_id") or uuid.uuid4())
        started = datetime.now(UTC)
        await recorder.record_agent_run(
            AgentRunRecord(
                session_id=str(state.get("session_id") or ""),
                agent_run_id=agent_run_id,
                agent_name=agent_name,
                input_state_json=to_plain_data(state),
                status="started",
                started_at=started,
            )
        )
        monotonic_start = time.monotonic()
        try:
            update = await node(state)
        except Exception as exc:
            await recorder.record_agent_run(
                AgentRunRecord(
                    session_id=str(state.get("session_id") or ""),
                    agent_run_id=agent_run_id,
                    agent_name=agent_name,
                    input_state_json=to_plain_data(state),
                    status="failed",
                    started_at=started,
                    finished_at=datetime.now(UTC),
                    error_message=str(exc),
                )
            )
            raise

        update = await _maybe_attach_validation(agent_name, update, settings.structured_output_enabled)

        await recorder.record_agent_run(
            AgentRunRecord(
                session_id=str(state.get("session_id") or ""),
                agent_run_id=agent_run_id,
                agent_name=agent_name,
                input_state_json=to_plain_data(state),
                output_state_json=to_plain_data(update),
                status="completed",
                started_at=started,
                finished_at=datetime.now(UTC),
            )
        )
        await _record_trace_artifacts(recorder, agent_name, agent_run_id, state, update, monotonic_start)
        return update

    return wrapped


async def _maybe_attach_validation(agent_name: str, update: dict, enabled: bool) -> dict:
    if not enabled or agent_name not in {"risk_assessor", "plan_generator", "resource_dispatcher", "execution_monitor"}:
        return update
    validation = await validate_agent_output(agent_name, _extract_structured_payload(agent_name, update))
    enriched = dict(update)
    enriched["output_validation"] = {
        "valid": validation.valid,
        "errors": validation.errors,
        "raw_output": to_plain_data(validation.raw_output),
    }
    return enriched


def _extract_structured_payload(agent_name: str, update: dict) -> dict:
    if agent_name == "risk_assessor":
        assessment = to_plain_data(update.get("risk_assessment") or {})
        score = float(assessment.get("risk_score") or 0.0)
        if score > 1:
            score = score / 100
        return {
            "risk_level": assessment.get("risk_level", "none"),
            "risk_score": score,
            "affected_stations": assessment.get("affected_stations") or [],
            "response_level": assessment.get("response_level") or "",
            "reasoning": assessment.get("reasoning") or "",
            "citations": assessment.get("citations") or [],
        }
    if agent_name == "plan_generator":
        plan = to_plain_data(update.get("emergency_plan") or {})
        return {
            "actions": plan.get("actions") or [],
            "resources": plan.get("resources") or [],
            "notifications": plan.get("notifications") or [],
            "trigger_conditions": plan.get("trigger_conditions") or "",
            "citations": plan.get("citations") or [],
        }
    if agent_name == "resource_dispatcher":
        resources = []
        for item in to_plain_data(update.get("resource_plan") or []):
            resources.append({
                "resource_id": item.get("resource_id") or item.get("resource_name") or "candidate",
                "quantity": item.get("quantity") or 1,
                "status": item.get("status") or "pending",
                "source_location": item.get("source_location") or "",
                "target_location": item.get("target_location") or "",
            })
        return {"resource_plan": resources}
    if agent_name == "execution_monitor":
        progress = to_plain_data(update.get("execution_progress") or {})
        return {
            "progress_pct": progress.get("progress_pct") or 0,
            "blocked_actions": progress.get("blocked_actions") or progress.get("issues") or [],
            "recommendations": progress.get("recommendations") or [],
        }
    return update


async def _record_trace_artifacts(
    recorder: Any,
    agent_name: str,
    agent_run_id: str,
    state: dict,
    update: dict,
    monotonic_start: float,
) -> None:
    session_id = str(state.get("session_id") or update.get("session_id") or "")
    for trace in update.get("execution_traces") or []:
        if trace.get("phase") != "tool_call" and not trace.get("tool_name"):
            continue
        metadata = trace.get("metadata") or {}
        await recorder.record_tool_call(
            ToolCallRecord(
                agent_run_id=agent_run_id,
                tool_name=str(trace.get("tool_name") or trace.get("title") or "unknown"),
                input_json={"summary": metadata.get("input_summary", "")},
                output_json={"summary": metadata.get("output_summary", ""), "detail": trace.get("detail", "")},
                success=str(trace.get("status") or "completed") != "failed",
                latency_ms=int(metadata.get("duration_ms") or 0),
                error_message=str(trace.get("detail") or "") if trace.get("status") == "failed" else None,
            )
        )

    for evidence in update.get("evidence") or update.get("evidence_context") or []:
        payload = to_plain_data(evidence)
        await recorder.record_evidence_trace(
            EvidenceTraceRecord(
                session_id=session_id,
                citation_id=str(payload.get("citation_id") or ""),
                document_id=str(payload.get("document_id") or payload.get("document_title") or ""),
                chunk_id=str(payload.get("chunk_id") or payload.get("citation_id") or ""),
                score=float(payload.get("score") or 0.0),
                used_by_agent=agent_name,
                used_in_field="evidence_context",
            )
        )

    if update.get("routing_decision"):
        await recorder.record_decision(
            DecisionLogRecord(
                session_id=session_id,
                decision_type="routing",
                decision_json=to_plain_data(update["routing_decision"]),
                evidence_ids=[],
                human_approved=not bool(update.get("human_confirmation_required")),
            )
        )

    if update.get("active_skill_id"):
        await recorder.record_skill_run(
            SkillRunRecord(
                skill_id=str(update.get("active_skill_id")),
                skill_version="1.0",
                session_id=session_id,
                agent_run_id=agent_run_id,
                input_json=to_plain_data(state),
                output_json=to_plain_data(update),
                quality_check_result=to_plain_data(update.get("skill_quality_results") or []),
            )
        )

    # Ensure monotonic_start is used to avoid future refactors removing timing.
    _ = time.monotonic() - monotonic_start
