"""Plan reviewer agent for compliance checks."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.config import get_settings
from app.rag.models import MetadataFilter
from app.rag.service import build_evidence, search_knowledge_base
from app.state import to_plain_data


class ViolationDetail(BaseModel):
    rule_id: str
    description: str
    severity: str
    cited_source: str


class ComplianceResult(BaseModel):
    compliant: bool
    violations: list[ViolationDetail] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    cited_regulations: list[dict] = Field(default_factory=list)
    status: str = "completed"


async def plan_reviewer_node(state: dict) -> dict:
    plan = state.get("emergency_plan")
    if not get_settings().plan_reviewer_enabled:
        result = ComplianceResult(compliant=True, status="skipped")
        return {"current_agent": "plan_reviewer", "compliance_result": result.model_dump(mode="json")}

    query = str(state.get("user_query") or getattr(plan, "plan_name", "") or "防汛应急预案合规校验")
    metadata_filter = MetadataFilter(doc_type="regulation")
    results = await search_knowledge_base(query, top_k=5, metadata_filter=metadata_filter)
    evidence = build_evidence(results)
    cited = [to_plain_data(item) for item in evidence]

    violations: list[ViolationDetail] = []
    if not plan:
        violations.append(
            ViolationDetail(
                rule_id="plan_missing",
                description="缺少可校验的应急预案",
                severity="error",
                cited_source="system",
            )
        )

    result = ComplianceResult(
        compliant=not violations,
        violations=violations,
        suggestions=[] if not violations else ["补充预案后重新校验"],
        cited_regulations=cited,
        status="completed",
    )
    update: dict = {
        "current_agent": "plan_reviewer",
        "compliance_result": result.model_dump(mode="json"),
        "evidence_context": evidence,
        "evidence": evidence,
    }
    if violations:
        update["plan_requires_revision"] = True
    return update
