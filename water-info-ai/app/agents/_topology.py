"""Dynamic topology profiles for supervisor routing.

When ``DYNAMIC_TOPOLOGY_ENABLED=true``, the supervisor uses
``select_profile()`` to pick the best-matching topology profile
based on intent, safety level, and answer policy.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ProfileMatch:
    profile_name: str
    priority: int
    reason: str


@dataclass
class TopologyProfile:
    name: str
    priority: int
    required_agents: list[str]
    skip_agents: list[str] = field(default_factory=list)
    description: str = ""

    def matches(
        self,
        intent: str,
        safety_level: str,
        answer_policy: dict,
        has_data: bool,
        has_risk: bool,
        has_plan: bool,
    ) -> ProfileMatch | None:
        """Return a ProfileMatch if this profile applies, else None."""
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Built-in profiles (priority ascending = lowest first = fallback)
# ---------------------------------------------------------------------------

class DefaultProfile(TopologyProfile):
    """Catch-all: never matches explicitly — used as final fallback."""
    def __init__(self) -> None:
        super().__init__(
            name="default",
            priority=0,
            required_agents=[],
            description="Default pass-through; no topology modification.",
        )

    def matches(self, **_: object) -> ProfileMatch | None:
        return ProfileMatch(self.name, self.priority, "default fallback")


class GeneralChatFastPath(TopologyProfile):
    """Short-circuit for general chat — skip all analysis agents."""
    def __init__(self) -> None:
        super().__init__(
            name="general_chat_fast_path",
            priority=100,
            required_agents=[],
            skip_agents=[
                "data_analyst", "risk_assessor", "plan_generator",
                "resource_dispatcher", "notification", "execution_monitor",
                "knowledge_retriever", "plan_reviewer", "safety_checker",
            ],
            description="Route general chat directly to conversation_assistant.",
        )

    def matches(
        self,
        intent: str,
        safety_level: str,
        answer_policy: dict,
        **_: object,
    ) -> ProfileMatch | None:
        if intent == "general_chat":
            return ProfileMatch(self.name, self.priority, "intent=general_chat")
        return None


class DataOnlyFastPath(TopologyProfile):
    """Skip risk/plan/dispatch when the user only wants raw data."""
    def __init__(self) -> None:
        super().__init__(
            name="data_only_fast_path",
            priority=200,
            required_agents=["data_analyst"],
            skip_agents=[
                "risk_assessor", "plan_generator", "resource_dispatcher",
                "notification", "execution_monitor", "plan_reviewer", "safety_checker",
            ],
            description="Data-only queries skip risk/plan/dispatch.",
        )

    def matches(
        self,
        intent: str,
        safety_level: str,
        answer_policy: dict,
        **_: object,
    ) -> ProfileMatch | None:
        if answer_policy.get("data_only"):
            return ProfileMatch(self.name, self.priority, "answer_policy.data_only=true")
        return None


class CriticalResponseWithReview(TopologyProfile):
    """Full pipeline with mandatory review and safety check for critical responses."""
    def __init__(self) -> None:
        super().__init__(
            name="critical_response_with_review",
            priority=900,
            required_agents=[
                "data_analyst", "risk_assessor", "plan_generator",
                "plan_reviewer", "safety_checker", "resource_dispatcher", "notification",
            ],
            description="Critical safety level requires full pipeline with review.",
        )

    def matches(
        self,
        intent: str,
        safety_level: str,
        answer_policy: dict,
        has_data: bool,
        has_risk: bool,
        has_plan: bool,
    ) -> ProfileMatch | None:
        if safety_level == "critical":
            return ProfileMatch(self.name, self.priority, "safety_level=critical")
        return None


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_PROFILES: list[TopologyProfile] = [
    CriticalResponseWithReview(),  # priority 900
    DataOnlyFastPath(),            # priority 200
    GeneralChatFastPath(),         # priority 100
    DefaultProfile(),              # priority 0
]


def select_profile(
    intent: str,
    safety_level: str,
    answer_policy: dict,
    has_data: bool = False,
    has_risk: bool = False,
    has_plan: bool = False,
) -> ProfileMatch:
    """Select the highest-priority matching profile.

    Profiles are checked in descending priority order (highest first).
    The first match wins.  DefaultProfile always matches as fallback.
    """
    for profile in _PROFILES:
        match = profile.matches(
            intent=intent,
            safety_level=safety_level,
            answer_policy=answer_policy,
            has_data=has_data,
            has_risk=has_risk,
            has_plan=has_plan,
        )
        if match is not None:
            return match
    # Should never reach here since DefaultProfile always matches
    return ProfileMatch("default", 0, "fallback")


def get_profile(name: str) -> TopologyProfile | None:
    for p in _PROFILES:
        if p.name == name:
            return p
    return None
