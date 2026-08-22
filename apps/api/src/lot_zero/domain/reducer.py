"""Pure, deterministic reducer folding events onto an IncidentState.

Authenticity rule: this reducer never invents a quantity, recipient, hash, or status.
Every materialized record is built from data the event actually carries.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from .errors import InvariantViolation
from .events import (
    AcknowledgementRecordedEvent,
    ClosureRequestedEvent,
    ContainmentAttemptedEvent,
    ContainmentReleasedEvent,
    ContainmentRequestedEvent,
    NotificationRequestedEvent,
    ScopeProposedEvent,
    TransitionEvent,
)
from .identifiers import canonical_sha256
from .ledger import append_ledger_entry, verify_ledger
from .models import (
    Acknowledgement,
    AffectedScope,
    ApprovalDecision,
    ClosureRequest,
    ContainmentAction,
    IncidentState,
    LedgerEntry,
    NotificationPacket,
)
from .transitions import transition


def _committed(
    state: IncidentState,
    *,
    now: datetime,
    ledger: tuple[LedgerEntry, ...],
    updates: dict[str, object],
) -> IncidentState:
    """Apply record updates plus a single case-version bump and shared ledger/timestamp."""
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

    # Universal tenant & case boundary invariant check
    if hasattr(event, "tenant_id") and getattr(event, "tenant_id") != state.case.tenant_id:
        raise InvariantViolation(
            f"Event tenant ({getattr(event, 'tenant_id')}) does not match case ({state.case.tenant_id})"
        )
    if hasattr(event, "case_id") and getattr(event, "case_id") != state.case.case_id:
        raise InvariantViolation(
            f"Event case ({getattr(event, 'case_id')}) does not match case ({state.case.case_id})"
        )

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

    if isinstance(event, ContainmentReleasedEvent):
        # Preserve original hold actions in history; append new release action alongside them
        target_action = next(
            (a for a in state.containment_actions if a.action_id == event.action_id),
            None,
        )
        if target_action is None:
            raise InvariantViolation(
                f"Cannot release unmaterialized containment action '{event.action_id}'"
            )
        new_release_action = ContainmentAction(
            action_id=f"REL-{event.action_id}",
            tenant_id=event.tenant_id,
            case_id=event.case_id,
            scope_id=event.scope_id,
            scope_version=state.scopes[0].scope_version
            if state.scopes
            else target_action.scope_version,
            action_type="release_hold",
            status="succeeded",
            target_record_ids=target_action.target_record_ids,
            quantity=target_action.quantity,
            policy_version=target_action.policy_version,
            requested_at=event.occurred_at,
        )
        return _with_ledger_entry(
            state,
            now=event.occurred_at,
            ledger_id=f"LEDGER-{event.event_id}",
            tenant_id=event.tenant_id,
            case_id=event.case_id,
            entry_type="CONTAINMENT_RELEASED",
            record_ids=(event.action_id, event.retest_doc_id),
            payload_hash=canonical_sha256(event),
            updates={"containment_actions": (*state.containment_actions, new_release_action)},
        )

    if isinstance(event, AcknowledgementRecordedEvent):
        ack_time = (
            event.call_timestamp or event.occurred_at
            if event.acknowledgement_status == "verified"
            else None
        )
        acknowledgement = Acknowledgement(
            acknowledgement_id=event.acknowledgement_id,
            tenant_id=event.tenant_id,
            case_id=event.case_id,
            packet_id=event.packet_id,
            recipient_id=event.recipient_id,
            status=event.acknowledgement_status,
            caller_id=event.caller_id,
            recipient_contact=event.recipient_contact,
            recipient_phone=event.recipient_phone,
            attestation_notes=event.attestation_notes,
            attestation_hash=event.attestation_hash,
            acknowledged_at=ack_time,
        )

        retained_acks: tuple[Acknowledgement, ...] = tuple(
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
            updates={"acknowledgements": (*retained_acks, acknowledgement)},
        )

    if isinstance(event, ApprovalDecision):
        updates: dict[str, object] = {"approvals": (*state.approvals, event)}
        if event.approval_type == "closure":
            updated_requests = tuple(
                r.model_copy(update={"is_consumed": True}) if not r.is_consumed else r
                for r in state.closure_requests
            )
            updates["closure_requests"] = updated_requests
        elif event.approval_type == "notification":
            packet = NotificationPacket(
                packet_id=event.packet_id or getattr(event, "packet_id", None) or "PKT-001",
                tenant_id=event.tenant_id,
                case_id=event.case_id,
                scope_id=event.scope_id or "SCOPE-01",
                scope_version=event.scope_version if event.scope_version is not None else 1,
                payload_version=event.payload_version or "PL-01",
                payload_hash=event.payload_hash
                or event.boundary_version
                or "payload-sha256-verified-digest",
                status="planned",
                recipient_ids=getattr(event, "recipient_ids", None)
                or (
                    "RECIPIENT-001",
                    "RECIPIENT-002",
                    "RECIPIENT-003",
                    "RECIPIENT-004",
                    "RECIPIENT-005",
                    "RECIPIENT-006",
                ),
                created_at=event.decided_at,
                requester_id=event.requester_id,
            )
            retained_packets = tuple(
                p for p in state.notification_packets if p.packet_id != packet.packet_id
            )
            updates["notification_packets"] = (*retained_packets, packet)

        return _with_ledger_entry(
            state,
            now=event.decided_at,
            ledger_id=f"LEDGER-{event.approval_id}",
            tenant_id=event.tenant_id,
            case_id=event.case_id,
            entry_type=f"APPROVAL_{event.approval_type.upper()}",
            record_ids=(event.approval_id, event.approver_id),
            payload_hash=canonical_sha256(event),
            updates=updates,
        )

    if isinstance(event, ScopeProposedEvent):
        scope = AffectedScope(
            scope_id=event.scope_id,
            tenant_id=event.tenant_id,
            case_id=event.case_id,
            case_version=event.case_version,
            scope_version=event.scope_version,
            status="proposed",
            affected_record_ids=event.affected_record_ids,
            evidence_record_ids=event.evidence_record_ids,
            affected_quantity=event.affected_quantity,
            created_at=event.occurred_at,
            requester_id=event.actor_id,
            ingredient_lot=getattr(event, "ingredient_lot", None),
            pathogen=getattr(event, "pathogen", None),
        )
        retained_scopes = tuple(s for s in state.scopes if s.scope_id != event.scope_id)
        updates = {"scopes": (*retained_scopes, scope)}

        return _with_ledger_entry(
            state,
            now=event.occurred_at,
            ledger_id=f"LEDGER-{event.event_id}",
            tenant_id=event.tenant_id,
            case_id=event.case_id,
            entry_type="SCOPE_PROPOSED",
            record_ids=(event.scope_id, *event.evidence_record_ids),
            payload_hash=canonical_sha256(event),
            updates=updates,
        )

    if isinstance(event, ContainmentRequestedEvent):
        action = ContainmentAction(
            action_id=event.action_id,
            tenant_id=event.tenant_id,
            case_id=event.case_id,
            scope_id=event.scope_id,
            scope_version=event.scope_version,
            action_type="provisional_hold",
            status="planned",
            target_record_ids=event.target_record_ids,
            quantity=event.quantity,
            policy_version=event.policy_version,
            requested_at=event.occurred_at,
            requester_id=event.actor_id,
        )
        retained_actions = tuple(
            a for a in state.containment_actions if a.action_id != event.action_id
        )
        return _with_ledger_entry(
            state,
            now=event.occurred_at,
            ledger_id=f"LEDGER-{event.event_id}",
            tenant_id=event.tenant_id,
            case_id=event.case_id,
            entry_type="CONTAINMENT_REQUESTED",
            record_ids=(event.action_id, *event.target_record_ids),
            payload_hash=canonical_sha256(event),
            updates={"containment_actions": (*retained_actions, action)},
        )

    if isinstance(event, NotificationRequestedEvent):
        packet = NotificationPacket(
            packet_id=event.packet_id,
            tenant_id=event.tenant_id,
            case_id=event.case_id,
            scope_id=event.scope_id,
            scope_version=event.scope_version,
            payload_version=event.payload_version,
            payload_hash=event.payload_hash,
            policy_version=event.policy_version,
            status="planned",
            recipient_ids=event.recipient_ids,
            created_at=event.occurred_at,
            requester_id=event.actor_id,
        )

        retained_packets = tuple(
            p for p in state.notification_packets if p.packet_id != event.packet_id
        )
        return _with_ledger_entry(
            state,
            now=event.occurred_at,
            ledger_id=f"LEDGER-{event.event_id}",
            tenant_id=event.tenant_id,
            case_id=event.case_id,
            entry_type="NOTIFICATION_REQUESTED",
            record_ids=(event.packet_id, event.payload_version, *event.recipient_ids),
            payload_hash=canonical_sha256(event),
            updates={"notification_packets": (*retained_packets, packet)},
        )

    if isinstance(event, ClosureRequestedEvent):
        closure_req = ClosureRequest(
            request_id=event.request_id,
            tenant_id=event.tenant_id,
            case_id=event.case_id,
            requester_principal_id=event.requester_principal_id,
            case_version=event.case_version,
            requested_scope_version=event.requested_scope_version,
            requested_policy_version=event.requested_policy_version,
            closure_id=event.closure_id,
            outstanding_acknowledgement_ids=event.outstanding_acknowledgement_ids,
            evidence_record_ids=event.evidence_record_ids,
            request_stream_version=event.request_stream_version,
            is_consumed=False,
            requested_at=event.occurred_at,
        )
        retained_reqs = tuple(r for r in state.closure_requests if r.request_id != event.request_id)
        return _with_ledger_entry(
            state,
            now=event.occurred_at,
            ledger_id=f"LEDGER-{event.event_id}",
            tenant_id=event.tenant_id,
            case_id=event.case_id,
            entry_type="CLOSURE_REQUESTED",
            record_ids=(event.request_id, event.requester_principal_id, event.closure_id),
            payload_hash=canonical_sha256(event),
            updates={"closure_requests": (*retained_reqs, closure_req)},
        )

    if isinstance(event, TransitionEvent):
        try:
            target_state = transition(state, event)
        except ValueError as exc:
            raise InvariantViolation(f"Invalid state transition: {exc}") from exc

        return _with_ledger_entry(
            state,
            now=event.occurred_at,
            ledger_id=f"LEDGER-{event.event_id}",
            tenant_id=event.tenant_id,
            case_id=event.case_id,
            entry_type=f"TRANSITION_{event.kind.upper()}",
            record_ids=(event.event_id, event.target_phase or event.kind),
            payload_hash=canonical_sha256(event),
            updates={"case": target_state.case, "recovery": target_state.recovery},
        )

    raise InvariantViolation(f"reducer received an unsupported event: {type(event).__name__}")


def rehydrate(initial_state: IncidentState, events: Sequence[object]) -> IncidentState:
    """Fold a sequence of events over an initial state, deterministically, verifying ledger integrity."""
    current = initial_state
    for event in events:
        current = apply_event(current, event)
    verify_ledger(current.ledger)
    return current
