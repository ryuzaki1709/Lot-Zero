"""Closed primary-phase and orthogonal recovery transitions."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field, model_validator

from .models import DomainRecord, Identifier, IncidentState, NonNegativeVersion, RecoveryState

type PrimaryPhase = Literal[
    "signal_received",
    "scope_review",
    "provisional_containment",
    "action_review",
    "ack_monitoring",
    "effectiveness_check",
    "closed",
]

_ALLOWED_PRIMARY_TARGETS: dict[PrimaryPhase, PrimaryPhase] = {
    "signal_received": "scope_review",
    "scope_review": "provisional_containment",
    "provisional_containment": "action_review",
    "action_review": "ack_monitoring",
    "ack_monitoring": "effectiveness_check",
    "effectiveness_check": "closed",
}


class TransitionEvent(DomainRecord):
    """A state-only event; it carries no external-action instruction."""

    event_id: Identifier
    tenant_id: Identifier
    case_id: Identifier
    case_version: NonNegativeVersion
    kind: Literal["advance", "recovery_entered", "recovery_returned"]
    target_phase: PrimaryPhase | None = None
    recovery_status: Literal["needs_information", "failed_retryable", "blocked"] | None = None
    parent_phase: PrimaryPhase | None = None
    return_phase: PrimaryPhase | None = None
    reason_record_ids: Annotated[tuple[Identifier, ...], Field(min_length=1)] | None = None
    retry_attempt: NonNegativeVersion | None = None
    retry_limit: NonNegativeVersion | None = None
    occurred_at: datetime

    @model_validator(mode="after")
    def validate_shape(self) -> TransitionEvent:
        if self.kind == "advance":
            if self.target_phase is None:
                raise ValueError("advance events require target_phase")
            if any(
                value is not None
                for value in (
                    self.recovery_status,
                    self.parent_phase,
                    self.return_phase,
                    self.reason_record_ids,
                    self.retry_attempt,
                    self.retry_limit,
                )
            ):
                raise ValueError("advance events cannot carry recovery fields")
        elif self.kind == "recovery_entered":
            if (
                self.recovery_status is None
                or self.parent_phase is None
                or self.return_phase is None
                or self.reason_record_ids is None
            ):
                raise ValueError("recovery entry requires status, phases, and reason records")
            if self.target_phase is not None:
                raise ValueError("recovery events cannot carry target_phase")
            if self.recovery_status == "failed_retryable":
                if self.retry_attempt is None or self.retry_limit is None:
                    raise ValueError("retryable recovery requires bounded retry state")
                if self.retry_attempt > self.retry_limit:
                    raise ValueError("retry attempt cannot exceed retry limit")
            elif self.retry_attempt is not None or self.retry_limit is not None:
                raise ValueError("only retryable recovery carries retry state")
        else:
            if self.parent_phase is None or self.return_phase is None:
                raise ValueError("recovery return requires parent and return phases")
            if any(
                value is not None
                for value in (
                    self.target_phase,
                    self.recovery_status,
                    self.reason_record_ids,
                    self.retry_attempt,
                    self.retry_limit,
                )
            ):
                raise ValueError("recovery return carries only its phases")
        return self


def _validate_boundary(state: IncidentState, event: TransitionEvent) -> None:
    if event.tenant_id != state.case.tenant_id:
        raise ValueError("event tenant does not match incident state")
    if event.case_id != state.case.case_id:
        raise ValueError("event case does not match incident state")
    if event.case_version != state.case.case_version:
        raise ValueError("stale event case version")


def _advance(state: IncidentState, event: TransitionEvent) -> IncidentState:
    if state.recovery is not None:
        raise ValueError("primary transition is blocked by recovery")
    current_phase = state.case.phase
    expected_target = _ALLOWED_PRIMARY_TARGETS.get(current_phase)
    if event.target_phase != expected_target:
        raise ValueError("invalid primary transition")
    updated_case = state.case.model_copy(
        update={
            "phase": event.target_phase,
            "case_version": state.case.case_version + 1,
            "updated_at": event.occurred_at,
        }
    )
    return state.model_copy(update={"case": updated_case, "updated_at": event.occurred_at})


def _enter_recovery(state: IncidentState, event: TransitionEvent) -> IncidentState:
    if state.recovery is not None:
        raise ValueError("incident is already in recovery")
    if event.parent_phase != state.case.phase or event.return_phase != state.case.phase:
        raise ValueError("recovery must return to its current parent phase")
    recovery = RecoveryState(
        status=event.recovery_status,
        parent_phase=event.parent_phase,
        return_phase=event.return_phase,
        reason_record_ids=event.reason_record_ids,
        retry_attempt=event.retry_attempt,
        retry_limit=event.retry_limit,
    )
    updated_case = state.case.model_copy(
        update={"case_version": state.case.case_version + 1, "updated_at": event.occurred_at}
    )
    return state.model_copy(
        update={"case": updated_case, "recovery": recovery, "updated_at": event.occurred_at}
    )


def _return_from_recovery(state: IncidentState, event: TransitionEvent) -> IncidentState:
    recovery = state.recovery
    if recovery is None:
        raise ValueError("incident is not in recovery")
    if (
        event.parent_phase != recovery.parent_phase
        or event.return_phase != recovery.return_phase
        or recovery.return_phase != state.case.phase
    ):
        raise ValueError("recovery return cannot skip a primary phase")
    updated_case = state.case.model_copy(
        update={"case_version": state.case.case_version + 1, "updated_at": event.occurred_at}
    )
    return state.model_copy(
        update={"case": updated_case, "recovery": None, "updated_at": event.occurred_at}
    )


def transition(state: IncidentState, event: TransitionEvent) -> IncidentState:
    """Apply one valid, case-bound state transition without touching the input state."""

    _validate_boundary(state, event)
    if event.kind == "advance":
        return _advance(state, event)
    if event.kind == "recovery_entered":
        return _enter_recovery(state, event)
    return _return_from_recovery(state, event)
