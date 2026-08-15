"""Pure, deterministic reducer folding events onto an IncidentState.

Authenticity rule: this reducer never invents a quantity, recipient, hash, or status.
Every materialized record is built from data the event actually carries. Where an event
does not yet carry enough authentic data to build a full record (scope, notification, and
closure in this build), the reducer records tamper-evident ledger provenance only and
leaves the projection explicitly unmaterialized rather than fabricating values.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from .errors import InvariantViolation
from .events import (
    AcknowledgementRecordedEvent,
    ClosureRequestedEvent,
    ContainmentAttemptedEvent,
    ContainmentRequestedEvent,
    NotificationRequestedEvent,
    ScopeProposedEvent,
)
from .identifiers import canonical_sha256
from .ledger import append_ledger_entry
from .models import (
    Acknowledgement,
    ApprovalDecision,
    ContainmentAction,
    IncidentState,
    LedgerEntry,
)
from .transitions import TransitionEvent, transition


def _committed(
    state: IncidentState,
    *,
    now: datetime,
    ledger: tuple[LedgerEntry, ...],
    updates: dict[str, object],
) -> IncidentState:
    """Apply record updates plus a single case-version bump and shared ledger/timestamp.

    ``case_version`` doubles as the aggregate stream version for optimistic concurrency:
    exactly one increment per applied event keeps compare-and-set append checks honest.
    """

    updated_case = state.case.model_copy(
        update={"case_version": state.case.case_version + 1, "updated_at": now}
    )
    return state.model_copy(
        update={"case": updated_case, "ledger": ledger, "updated_at": now, **updates}
    )


def _with_ledger_entry(
    state: IncidentState,
    *,
    now: datetime,
    ledger_id: str,
    tenant_id: str,
    case_id: str,
    entry_type: str,
    record_ids: Sequence[str],
    payload_hash: str,
    updates: dict[str, object] | None = None,
) -> IncidentState:
    ledger = append_ledger_entry(
        state.ledger,
        ledger_id=ledger_id,
        tenant_id=tenant_id,
        case_id=case_id,
        entry_type=entry_type,
        record_ids=record_ids,
        payload_hash=payload_hash,
        created_at=now,
    )
    return _committed(state, now=now, ledger=ledger, updates=updates or {})


def apply_event(state: IncidentState, event: object) -> IncidentState:
    """Apply a single event to the state, returning a new immutable state."""

    # Phase and recovery transitions own their own version bump and validation.
    if isinstance(event, TransitionEvent):
        return transition(state, event)

    if isinstance(event, ContainmentAttemptedEvent):
        action: ContainmentAction = event.action
        if action.tenant_id != state.case.tenant_id or action.case_id != state.case.case_id:
            raise InvariantViolation("containment action must match the incident boundary")
        retained = tuple(
            existing
            for existing in state.containment_actions
            if existing.action_id != action.action_id
        )
        return _with_ledger_entry(
            state,
            now=event.occurred_at,
            ledger_id=f"LEDGER-{event.event_id}",
            tenant_id=event.tenant_id,
            case_id=event.case_id,
            entry_type="CONTAINMENT_ATTEMPTED",
            record_ids=(action.action_id, *action.target_record_ids),
            payload_hash=canonical_sha256(event),
            updates={"containment_actions": (*retained, action)},
        )

    if isinstance(event, AcknowledgementRecordedEvent):
        acknowledgement = Acknowledgement(
            acknowledgement_id=event.acknowledgement_id,
            tenant_id=event.tenant_id,
            case_id=event.case_id,
            packet_id=event.packet_id,
            recipient_id=event.recipient_id,
            status=event.acknowledgement_status,
            acknowledged_at=(
                event.occurred_at if event.acknowledgement_status == "verified" else None
            ),
        )
        retained = tuple(
            existing
            for existing in state.acknowledgements
            if existing.acknowledgement_id != event.acknowledgement_id
        )
        return _with_ledger_entry(
            state,
            now=event.occurred_at,
            ledger_id=f"LEDGER-{event.event_id}",
            tenant_id=event.tenant_id,
            case_id=event.case_id,
            entry_type="ACKNOWLEDGEMENT_RECORDED",
            record_ids=(event.acknowledgement_id, event.recipient_id),
            payload_hash=canonical_sha256(event),
            updates={"acknowledgements": (*retained, acknowledgement)},
        )

    if isinstance(event, ApprovalDecision):
        return _with_ledger_entry(
            state,
            now=event.decided_at,
            ledger_id=f"LEDGER-{event.approval_id}",
            tenant_id=event.tenant_id,
            case_id=event.case_id,
            entry_type=f"APPROVAL_{event.approval_type.upper()}",
            record_ids=(event.approval_id, event.approver_id),
            payload_hash=canonical_sha256(event),
            updates={"approvals": (*state.approvals, event)},
        )

    # Provenance-only events: recorded in the hash-linked ledger, but not yet materialized
    # into projections because the event does not carry enough authentic data to do so
    # without invention. These are materialized in a later slice once the impact context
    # (scope) and payload content (notification) are threaded through.
    if isinstance(event, ScopeProposedEvent):
        return _with_ledger_entry(
            state,
            now=event.occurred_at,
            ledger_id=f"LEDGER-{event.event_id}",
            tenant_id=event.tenant_id,
            case_id=event.case_id,
            entry_type="SCOPE_PROPOSED",
            record_ids=(event.scope_id, *event.evidence_record_ids),
            payload_hash=canonical_sha256(event),
        )

    if isinstance(event, ContainmentRequestedEvent):
        return _with_ledger_entry(
            state,
            now=event.occurred_at,
            ledger_id=f"LEDGER-{event.event_id}",
            tenant_id=event.tenant_id,
            case_id=event.case_id,
            entry_type="CONTAINMENT_REQUESTED",
            record_ids=(event.action_id, *event.target_record_ids),
            payload_hash=canonical_sha256(event),
        )

    if isinstance(event, NotificationRequestedEvent):
        return _with_ledger_entry(
            state,
            now=event.occurred_at,
            ledger_id=f"LEDGER-{event.event_id}",
            tenant_id=event.tenant_id,
            case_id=event.case_id,
            entry_type="NOTIFICATION_REQUESTED",
            record_ids=(event.packet_id, event.payload_version),
            payload_hash=canonical_sha256(event),
        )

    if isinstance(event, ClosureRequestedEvent):
        return _with_ledger_entry(
            state,
            now=event.occurred_at,
            ledger_id=f"LEDGER-{event.event_id}",
            tenant_id=event.tenant_id,
            case_id=event.case_id,
            entry_type="CLOSURE_REQUESTED",
            record_ids=(event.closure_id, event.policy_version),
            payload_hash=canonical_sha256(event),
        )

    raise InvariantViolation(f"reducer received an unsupported event: {type(event).__name__}")


def rehydrate(initial_state: IncidentState, events: Sequence[object]) -> IncidentState:
    """Fold a sequence of events over an initial state, deterministically."""
    current = initial_state
    for event in events:
        current = apply_event(current, event)
    return current
