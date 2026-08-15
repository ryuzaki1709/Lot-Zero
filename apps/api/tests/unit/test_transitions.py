"""The incident phase table and recovery paths are closed and immutable."""

from datetime import UTC, datetime, timedelta

import pytest

from lot_zero.domain.models import IncidentState, RecallCase
from lot_zero.domain.transitions import TransitionEvent, transition

NOW = datetime(2026, 8, 14, 12, tzinfo=UTC)
TENANT = "EVAL-TENANT-01"
CASE = "EVAL-CASE-01"

ALLOWED_PRIMARY_TRANSITIONS = (
    ("signal_received", "scope_review"),
    ("scope_review", "provisional_containment"),
    ("provisional_containment", "action_review"),
    ("action_review", "ack_monitoring"),
    ("ack_monitoring", "effectiveness_check"),
    ("effectiveness_check", "closed"),
)


def state_for(phase: str, *, case_version: int = 3) -> IncidentState:
    case = RecallCase(
        case_id=CASE,
        tenant_id=TENANT,
        phase=phase,
        case_version=case_version,
        source_record_ids=("LAB-SIGNAL-20260814-001",),
        created_at=NOW,
        updated_at=NOW,
    )
    return IncidentState(case=case, updated_at=NOW)


def advance_event(source: str, target: str, *, case_version: int = 3) -> TransitionEvent:
    return TransitionEvent(
        event_id=f"EVENT-{source}-{target}",
        tenant_id=TENANT,
        case_id=CASE,
        case_version=case_version,
        kind="advance",
        target_phase=target,
        occurred_at=NOW + timedelta(minutes=1),
    )


@pytest.mark.parametrize(("source", "target"), ALLOWED_PRIMARY_TRANSITIONS)
def test_every_allowed_primary_transition_advances_one_phase(source: str, target: str) -> None:
    before = state_for(source)

    after = transition(before, advance_event(source, target))

    assert after.case.phase == target
    assert after.case.case_version == 4
    assert after.updated_at == NOW + timedelta(minutes=1)
    assert before.case.phase == source
    assert before.case.case_version == 3


@pytest.mark.parametrize(
    ("source", "target"),
    (("signal_received", "provisional_containment"), ("scope_review", "closed")),
)
def test_primary_phase_skips_are_rejected_without_changing_state(source: str, target: str) -> None:
    before = state_for(source)

    with pytest.raises(ValueError, match="invalid primary transition"):
        transition(before, advance_event(source, target))

    assert before.case.phase == source
    assert before.case.case_version == 3


@pytest.mark.parametrize("recovery_status", ("needs_information", "failed_retryable", "blocked"))
def test_each_recovery_status_returns_without_skipping_the_parent_phase(
    recovery_status: str,
) -> None:
    before = state_for("action_review")
    retry_fields = (
        {"retry_attempt": 1, "retry_limit": 2} if recovery_status == "failed_retryable" else {}
    )
    entered = transition(
        before,
        TransitionEvent(
            event_id="EVENT-RECOVERY-ENTER",
            tenant_id=TENANT,
            case_id=CASE,
            case_version=3,
            kind="recovery_entered",
            recovery_status=recovery_status,
            parent_phase="action_review",
            return_phase="action_review",
            reason_record_ids=("BLOCKER-001",),
            occurred_at=NOW + timedelta(minutes=1),
            **retry_fields,
        ),
    )
    resumed = transition(
        entered,
        TransitionEvent(
            event_id="EVENT-RECOVERY-RETURN",
            tenant_id=TENANT,
            case_id=CASE,
            case_version=4,
            kind="recovery_returned",
            parent_phase="action_review",
            return_phase="action_review",
            occurred_at=NOW + timedelta(minutes=2),
        ),
    )

    assert entered.case.phase == "action_review"
    assert entered.recovery is not None
    assert entered.recovery.status == recovery_status
    assert resumed.case.phase == "action_review"
    assert resumed.recovery is None


def test_recovery_cannot_return_to_a_different_primary_phase() -> None:
    before = state_for("scope_review")

    with pytest.raises(ValueError, match="recovery"):
        transition(
            before,
            TransitionEvent(
                event_id="EVENT-BAD-RECOVERY",
                tenant_id=TENANT,
                case_id=CASE,
                case_version=3,
                kind="recovery_entered",
                recovery_status="blocked",
                parent_phase="scope_review",
                return_phase="closed",
                reason_record_ids=("BLOCKER-002",),
                occurred_at=NOW + timedelta(minutes=1),
            ),
        )

    assert before.recovery is None


@pytest.mark.parametrize(
    "event_overrides",
    (
        {"tenant_id": "OTHER-TENANT"},
        {"case_id": "OTHER-CASE"},
        {"case_version": 2},
    ),
)
def test_stale_or_cross_boundary_event_is_rejected_without_mutating_state(
    event_overrides: dict[str, object],
) -> None:
    before = state_for("signal_received")
    event = advance_event("signal_received", "scope_review").model_copy(update=event_overrides)

    with pytest.raises(ValueError, match="tenant|case|stale"):
        transition(before, event)

    assert before.case.phase == "signal_received"
    assert before.case.case_version == 3
