"""Platform kernel foundation tests."""

from __future__ import annotations

import importlib
import uuid

import pytest


@pytest.fixture(autouse=True)
def clear_settings_cache():
    config = importlib.import_module("app.config")
    config.get_settings.cache_clear()
    yield
    config.get_settings.cache_clear()


def test_platform_feature_flags_default_to_disabled(monkeypatch):
    config = importlib.import_module("app.config")
    config.get_settings.cache_clear()
    for name in [
        "STRUCTURED_OUTPUT_ENABLED",
        "SKILL_REGISTRY_ENABLED",
        "DISPATCH_STATE_MACHINE_ENABLED",
        "AUDIT_TABLES_ENABLED",
        "PLAN_REVIEWER_ENABLED",
    ]:
        monkeypatch.delenv(name, raising=False)

    settings = config.get_settings()

    assert settings.structured_output_enabled is False
    assert settings.skill_registry_enabled is False
    assert settings.dispatch_state_machine_enabled is False
    assert settings.audit_tables_enabled is False
    assert settings.plan_reviewer_enabled is False


def test_platform_feature_flags_parse_environment(monkeypatch):
    config = importlib.import_module("app.config")
    config.get_settings.cache_clear()
    monkeypatch.setenv("STRUCTURED_OUTPUT_ENABLED", "true")
    monkeypatch.setenv("SKILL_REGISTRY_ENABLED", "1")
    monkeypatch.setenv("DISPATCH_STATE_MACHINE_ENABLED", "yes")
    monkeypatch.setenv("AUDIT_TABLES_ENABLED", "on")
    monkeypatch.setenv("PLAN_REVIEWER_ENABLED", "TRUE")

    settings = config.get_settings()

    assert settings.structured_output_enabled is True
    assert settings.skill_registry_enabled is True
    assert settings.dispatch_state_machine_enabled is True
    assert settings.audit_tables_enabled is True
    assert settings.plan_reviewer_enabled is True


def test_flood_graph_state_contains_only_additive_kernel_fields():
    from app.state import FloodGraphState

    annotations = FloodGraphState.__annotations__

    for field in [
        "agent_run_id",
        "routing_decision",
        "safety_level",
        "human_confirmation_required",
        "active_skill_id",
        "skill_agent_sequence",
        "skill_quality_results",
        "compliance_result",
        "safety_check_result",
        "pending_approvals",
        "dispatch_orders",
        "metadata_filter",
    ]:
        assert field in annotations


def test_routing_decision_sets_high_safety_confirmation_and_uuid():
    from app.schemas.routing import RoutingDecision, SafetyLevel

    decision = RoutingDecision(
        intent="resource_dispatch",
        next_agent="resource_dispatcher",
        reasoning="需要调度抢险物资",
        safety_level=SafetyLevel.HIGH,
    )

    assert decision.human_confirmation_required is True
    assert uuid.UUID(decision.agent_run_id).version == 4
