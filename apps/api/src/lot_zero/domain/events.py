"""Closed immutable event types emitted after domain decisions."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import Field, TypeAdapter

from .models import (
    ApprovalDecision,
    ContainmentAction,
    DomainRecord,
    Identifier,
    NonNegativeQuantity,
    NonNegativeVersion,
)
from .transitions import TransitionEvent


class EventRecord(DomainRecord):
    event_id: Identifier
    tenant_id: Identifier
    case_id: Identifier
    actor_id: Identifier
    case_version: NonNegativeVersion
    occurred_at: datetime


class ScopeProposedEvent(EventRecord):
    kind: Literal["scope_proposed"] = "scope_proposed"
    scope_id: Identifier
    scope_version: NonNegativeVersion
    affected_record_ids: tuple[Identifier, ...] = ()
    affected_quantity: NonNegativeQuantity = Decimal("0")
    evidence_record_ids: Annotated[tuple[Identifier, ...], Field(min_length=1)]


class ContainmentRequestedEvent(EventRecord):
    kind: Literal["containment_requested"] = "containment_requested"
    scope_id: Identifier
    scope_version: NonNegativeVersion
    action_id: Identifier
    policy_version: Identifier
    target_record_ids: Annotated[tuple[Identifier, ...], Field(min_length=1)]


class NotificationRequestedEvent(EventRecord):
    kind: Literal["notification_requested"] = "notification_requested"
    scope_id: Identifier
    scope_version: NonNegativeVersion
    packet_id: Identifier
    payload_version: Identifier
    policy_version: Identifier


class AcknowledgementRecordedEvent(EventRecord):
    kind: Literal["acknowledgement_recorded"] = "acknowledgement_recorded"
    packet_id: Identifier
    acknowledgement_id: Identifier
    recipient_id: Identifier
    acknowledgement_status: Literal["verified", "outstanding", "rejected"]
    caller_id: Identifier | None = None
    recipient_contact: Identifier | None = None
    recipient_phone: Identifier | None = None
    attestation_notes: Identifier | None = None
    attestation_hash: Identifier | None = None
    call_timestamp: datetime | None = None


class ClosureRequestedEvent(EventRecord):
    kind: Literal["closure_requested"] = "closure_requested"
    closure_id: Identifier
    policy_version: Identifier
    outstanding_acknowledgement_ids: tuple[Identifier, ...] = ()


class ContainmentAttemptedEvent(EventRecord):
    """One persisted attempt at a reserved containment action."""

    kind: Literal["containment_attempted"] = "containment_attempted"
    action: ContainmentAction


class ContainmentReleasedEvent(EventRecord):
    """One persisted inventory release on verified negative re-test."""

    kind: Literal["containment_released"] = "containment_released"
    action_id: Identifier
    scope_id: Identifier
    retest_doc_id: Identifier
    retest_doc_hash: Identifier


type EventValue = Annotated[
    ScopeProposedEvent
    | ContainmentRequestedEvent
    | NotificationRequestedEvent
    | AcknowledgementRecordedEvent
    | ClosureRequestedEvent
    | ContainmentAttemptedEvent
    | ContainmentReleasedEvent
    | TransitionEvent
    | ApprovalDecision,
    Field(discriminator="kind"),
]
Event = TypeAdapter(EventValue)
