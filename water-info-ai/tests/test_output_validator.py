"""Tests for the output consistency validator."""

from __future__ import annotations

from app.agents.output_validator import validate_final_response
from app.state import EmergencyAction, EmergencyPlan, RiskAssessment, RiskLevel


def test_validator_passes_for_general_chat_without_structured_payload():
    report = validate_final_response("你好，我是防汛 AI 助手。", {"intent": "general_chat"})
    assert report.ok
    assert report.issues == []


def test_validator_flags_risk_level_mismatch():
    state = {
        "intent": "risk_assessment",
        "risk_assessment": RiskAssessment(risk_level=RiskLevel.HIGH, risk_score=82.0),
    }
    report = validate_final_response("当前风险等级偏低，可以放心。", state)
    assert not report.ok
    assert any("风险等级" in issue for issue in report.issues)


def test_validator_passes_when_text_mentions_canonical_level():
    state = {
        "intent": "risk_assessment",
        "risk_assessment": RiskAssessment(risk_level=RiskLevel.HIGH, risk_score=82.0),
    }
    report = validate_final_response("综合判断：当前 high 风险，请加强巡查。", state)
    assert report.ok


def test_validator_flags_missing_plan_name():
    plan = EmergencyPlan(plan_id="EP-001", plan_name="城区防汛预案")
    state = {"intent": "plan_generation", "emergency_plan": plan}
    report = validate_final_response("已经形成预案，可以开始执行。", state)
    assert not report.ok
    assert any("城区防汛预案" in issue for issue in report.issues)


def test_validator_flags_action_count_mismatch():
    actions = [
        EmergencyAction(action_id=f"A-{i}", action_type="patrol", description="巡查")
        for i in range(3)
    ]
    plan = EmergencyPlan(plan_id="EP-001", plan_name="城区防汛预案", actions=actions)
    state = {"intent": "plan_generation", "emergency_plan": plan}
    report = validate_final_response("城区防汛预案 共 5 项措施已就绪。", state)
    assert not report.ok
    assert any("措施" in issue for issue in report.issues)


def test_validator_flags_duplicate_evidence_section():
    text = "## 证据片段\n- 片段一\n\n## 证据片段\n- 片段二"
    report = validate_final_response(text, {"intent": "general_chat"})
    assert not report.ok
    assert any("证据片段" in issue for issue in report.issues)


def test_validator_flags_empty_text():
    report = validate_final_response("", {"intent": "overview"})
    assert not report.ok
