"""Closed immutable event types emitted after domain decisions."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field, TypeAdapter

from .models import DomainRecord, Identifier, NonNegativeVersion


class EventRecord(DomainRecord):
    event_id: Identifier
    tenant_id: Identifier
    case_id: Identifier
    actor_id: Identifier
    case_version: NonNegativeVersion
    occurred_at: datetime


class ScopeProposedEvent(EventRecord):
    kind: Literal["scope_proposed"]
    scope_id: Identifier
    scope_version: NonNegativeVersion
    evidence_record_ids: Annotated[tuple[Identifier, ...], Field(min_length=1)]


class ContainmentRequestedEvent(EventRecord):
    kind: Literal["containment_requested"]
    scope_id: Identifier
    scope_version: NonNegativeVersion
    action_id: Identifier
    policy_version: Identifier
    target_record_ids: Annotated[tuple[Identifier, ...], Field(min_length=1)]


class NotificationRequestedEvent(EventRecord):
    kind: Literal["notification_requested"]
    scope_id: Identifier
    scope_version: NonNegativeVersion
    packet_id: Identifier
    payload_version: Identifier
    policy_version: Identifier


class AcknowledgementRecordedEvent(EventRecord):
    kind: Literal["acknowledgement_recorded"]
    packet_id: Identifier
    acknowledgement_id: Identifier
    recipient_id: Identifier
    acknowledgement_status: Literal["verified", "outstanding", "rejected"]


class ClosureRequestedEvent(EventRecord):
    kind: Literal["closure_requested"]
    closure_id: Identifier
    policy_version: Identifier
    outstanding_acknowledgement_ids: tuple[Identifier, ...] = ()


type EventValue = Annotated[
    ScopeProposedEvent
    | ContainmentRequestedEvent
    | NotificationRequestedEvent
    | AcknowledgementRecordedEvent
    | ClosureRequestedEvent,
    Field(discriminator="kind"),
]
Event = TypeAdapter(EventValue)
