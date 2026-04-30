"""Cross-checks the final response narrative against structured state fields."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.state import RiskLevel


@dataclass
class ValidationReport:
    ok: bool = True
    issues: list[str] = field(default_factory=list)


_RISK_LEVEL_KEYWORDS: dict[RiskLevel, tuple[str, ...]] = {
    RiskLevel.NONE: ("none", "无风险", "无明显风险"),
    RiskLevel.LOW: ("low", "低风险", "偏低", "iv级", "ⅳ级", "四级"),
    RiskLevel.MODERATE: ("moderate", "中风险", "中等", "iii级", "ⅲ级", "三级"),
    RiskLevel.HIGH: ("high", "高风险", "偏高", "ii级", "ⅱ级", "二级"),
    RiskLevel.CRITICAL: ("critical", "极高", "严重", "特别重大", "i级", "ⅰ级", "一级"),
}

_EVIDENCE_HEADING = "## 证据片段"

_COUNT_PATTERNS: tuple[tuple[str, str], ...] = (
    ("actions", r"共\s*(\d+)\s*项措施"),
    ("actions", r"(\d+)\s*项措施"),
    ("actions", r"共\s*(\d+)\s*条措施"),
    ("notifications", r"(\d+)\s*条通知"),
    ("resources", r"(\d+)\s*项资源"),
    ("resources", r"(\d+)\s*类资源"),
)


def _expected_level_keywords(level: RiskLevel) -> tuple[str, ...]:
    return _RISK_LEVEL_KEYWORDS.get(level, ())


def _other_level_keywords(level: RiskLevel) -> list[str]:
    others: list[str] = []
    for other_level, words in _RISK_LEVEL_KEYWORDS.items():
        if other_level == level:
            continue
        others.extend(words)
    return others


def _contains_any(text: str, words: tuple[str, ...] | list[str]) -> bool:
    return any(word and word in text for word in words)


def validate_final_response(text: str, state: dict) -> ValidationReport:
    """Compare narrative text against structured fields. Pure function, no I/O."""
    report = ValidationReport()
    if not text:
        report.ok = False
        report.issues.append("最终回复为空")
        return report

    intent = state.get("intent", "overview")
    assessment = state.get("risk_assessment")
    plan = state.get("emergency_plan")
    resources = state.get("resource_plan") or []
    notifications = state.get("notifications") or []

    # Dedup check applies to every intent — duplicated evidence sections are always wrong.
    if text.count(_EVIDENCE_HEADING) > 1:
        report.ok = False
        report.issues.append("证据片段被重复拼接")

    lowered = text.lower()

    # general_chat without structured payload skips the remaining structured checks.
    if intent == "general_chat" and not assessment and not plan:
        return report

    if assessment is not None:
        risk_level = getattr(assessment, "risk_level", None)
        if isinstance(risk_level, str):
            try:
                risk_level = RiskLevel(risk_level)
            except ValueError:
                risk_level = None
        if isinstance(risk_level, RiskLevel):
            expected = _expected_level_keywords(risk_level)
            others = _other_level_keywords(risk_level)
            mentions_expected = _contains_any(lowered, expected)
            mentions_other = _contains_any(lowered, others)
            if not mentions_expected and mentions_other:
                report.ok = False
                report.issues.append(
                    f"叙述中风险等级与结构化字段不一致，应体现 {risk_level.value}"
                )

    if plan is not None:
        plan_name = getattr(plan, "plan_name", "")
        if plan_name and plan_name not in text:
            report.ok = False
            report.issues.append(f"未提及预案名称《{plan_name}》")

        actions = getattr(plan, "actions", None) or []
        for kind, pattern in _COUNT_PATTERNS:
            match = re.search(pattern, text)
            if not match:
                continue
            stated = int(match.group(1))
            if kind == "actions" and stated != len(actions):
                report.ok = False
                report.issues.append(
                    f"叙述声称 {stated} 项措施，但实际预案动作为 {len(actions)} 条"
                )
            elif kind == "notifications" and stated != len(notifications):
                report.ok = False
                report.issues.append(
                    f"叙述声称 {stated} 条通知，但通知记录为 {len(notifications)} 条"
                )
            elif kind == "resources" and stated != len(resources):
                report.ok = False
                report.issues.append(
                    f"叙述声称 {stated} 项资源，但资源记录为 {len(resources)} 条"
                )

    return report
