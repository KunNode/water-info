"""Smoke tests for the supervisor-autogen-enhancements feature flags.

Verifies that the four new flags added in task 1.1 default to ``False`` when
their environment variables are unset and flip to ``True`` when each is set
to ``"true"``.

Validates: Requirements 1.2, 2.10, 3.8, 4.13, 5.7
"""

from __future__ import annotations

import pytest

from app.config import get_settings

# (Settings attribute, environment variable) pairs for the four new flags.
FLAG_PAIRS: list[tuple[str, str]] = [
    ("otel_enabled", "OTEL_ENABLED"),
    ("agent_contracts_enabled", "AGENT_CONTRACTS_ENABLED"),
    ("dynamic_topology_enabled", "DYNAMIC_TOPOLOGY_ENABLED"),
    ("hitl_enabled", "HITL_ENABLED"),
]


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    """get_settings is lru_cache-decorated; reset before and after each test."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_new_flags_default_false_when_env_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    for _, env_key in FLAG_PAIRS:
        monkeypatch.delenv(env_key, raising=False)
    get_settings.cache_clear()

    settings = get_settings()

    for attr, _ in FLAG_PAIRS:
        assert getattr(settings, attr) is False, f"{attr} should default to False"


@pytest.mark.parametrize("attr,env_key", FLAG_PAIRS)
def test_new_flag_flips_true_when_env_true(
    monkeypatch: pytest.MonkeyPatch, attr: str, env_key: str
) -> None:
    # Start from a clean slate: all four flags unset.
    for _, key in FLAG_PAIRS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv(env_key, "true")
    get_settings.cache_clear()

    settings = get_settings()

    assert getattr(settings, attr) is True, f"{attr} should be True when {env_key}=true"
    # Other flags remain False (no cross-contamination).
    for other_attr, other_key in FLAG_PAIRS:
        if other_attr == attr:
            continue
        assert getattr(settings, other_attr) is False, (
            f"{other_attr} should remain False when only {env_key} is set"
        )
