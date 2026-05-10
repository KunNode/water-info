"""Dispatch order lifecycle state machine."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, Field


class DispatchState(str, Enum):
    AI_DRAFT = "AI_DRAFT"
    APPROVED = "APPROVED"
    DISPATCHED = "DISPATCHED"
    ARRIVED = "ARRIVED"
    RETURNED = "RETURNED"
    CANCELLED = "CANCELLED"


VALID_TRANSITIONS: dict[DispatchState, set[DispatchState]] = {
    DispatchState.AI_DRAFT: {DispatchState.APPROVED, DispatchState.CANCELLED},
    DispatchState.APPROVED: {DispatchState.DISPATCHED, DispatchState.CANCELLED},
    DispatchState.DISPATCHED: {DispatchState.ARRIVED, DispatchState.CANCELLED},
    DispatchState.ARRIVED: {DispatchState.RETURNED},
}


class InvalidTransitionError(ValueError):
    def __init__(self, current: DispatchState, target: DispatchState):
        super().__init__(f"invalid dispatch transition: current={current.value}, target={target.value}")
        self.current = current
        self.target = target


class TransitionRecord(BaseModel):
    from_state: DispatchState
    to_state: DispatchState
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    operator_id: str
    reason: str


class DispatchStateMachine:
    def __init__(self, current_state: DispatchState = DispatchState.AI_DRAFT):
        self._state = current_state
        self._history: list[TransitionRecord] = []

    @property
    def state(self) -> DispatchState:
        return self._state

    @property
    def history(self) -> list[TransitionRecord]:
        return list(self._history)

    def can_transition(self, target: DispatchState) -> bool:
        return target in VALID_TRANSITIONS.get(self._state, set())

    def transition(self, target: DispatchState, operator_id: str, reason: str) -> TransitionRecord:
        if not self.can_transition(target):
            raise InvalidTransitionError(self._state, target)
        record = TransitionRecord(
            from_state=self._state,
            to_state=target,
            operator_id=operator_id,
            reason=reason,
        )
        self._state = target
        self._history.append(record)
        return record
