"""Strict, immutable records that make up an incident's operational truth."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
)

Identifier = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
NonNegativeVersion = Annotated[int, Field(ge=0)]


def _normalize_quantity(value: Decimal) -> Decimal:
    """Trim insignificant zeroes in time proportional to input digits, not exponent."""

    if not value.is_finite():
        raise ValueError("quantities must be finite")
    if value == 0:
        return Decimal("0")
    decimal_tuple = value.as_tuple()
    exponent = decimal_tuple.exponent
    if not isinstance(exponent, int):
        raise ValueError("quantities must be finite")
    if decimal_tuple.sign:
        raise ValueError("quantities must be non-negative")

    digits = decimal_tuple.digits
    trailing_zeroes = 0
    for digit in reversed(digits):
        if digit != 0:
            break
        trailing_zeroes += 1
    normalized_digits = digits[: len(digits) - trailing_zeroes]
    return Decimal((0, normalized_digits or (0,), exponent + trailing_zeroes))


NonNegativeQuantity = Annotated[
    Decimal,
    Field(ge=Decimal("0")),
    AfterValidator(_normalize_quantity),
]


class DomainRecord(BaseModel):
    """Base for records persisted by the local domain kernel."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("*", mode="after")
    @classmethod
    def require_timezone_aware_datetimes(cls, value: object) -> object:
        if isinstance(value, datetime) and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("persisted datetimes must be timezone-aware")
        return value


class RecallCase(DomainRecord):
    case_id: Identifier
    tenant_id: Identifier
    phase: Literal[
        "signal_received",
        "scope_review",
        "provisional_containment",
        "action_review",
        "ack_monitoring",
        "effectiveness_check",
        "closed",
    ]
    case_version: NonNegativeVersion
    source_record_ids: Annotated[tuple[Identifier, ...], Field(min_length=1)]
    created_at: datetime
    updated_at: datetime


class EvidenceSpan(DomainRecord):
    evidence_id: Identifier
    tenant_id: Identifier
    case_id: Identifier
    source_record_id: Identifier
    claim_type: Identifier
    start_offset: NonNegativeVersion
    end_offset: NonNegativeVersion
    captured_at: datetime


class AffectedScope(DomainRecord):
    scope_id: Identifier
    tenant_id: Identifier
    case_id: Identifier
    case_version: NonNegativeVersion
    scope_version: NonNegativeVersion
    status: Literal["proposed", "approved", "superseded"]
    affected_record_ids: Annotated[tuple[Identifier, ...], Field(min_length=1)]
    evidence_record_ids: Annotated[tuple[Identifier, ...], Field(min_length=1)]
    affected_quantity: NonNegativeQuantity
    created_at: datetime


class ImpactRecord(DomainRecord):
    impact_id: Identifier
    tenant_id: Identifier
    case_id: Identifier
    scope_id: Identifier
    record_id: Identifier
    record_type: Identifier
    quantity: NonNegativeQuantity
    affected: bool
    evidence_record_ids: Annotated[tuple[Identifier, ...], Field(min_length=1)]
    assessed_at: datetime


class ContainmentAction(DomainRecord):
    action_id: Identifier
    tenant_id: Identifier
    case_id: Identifier
    scope_id: Identifier
    scope_version: NonNegativeVersion
    action_type: Literal["provisional_hold", "release_hold"]
    status: Literal["planned", "in_flight", "succeeded", "failed", "unknown"]
    target_record_ids: Annotated[tuple[Identifier, ...], Field(min_length=1)]
    quantity: NonNegativeQuantity
    policy_version: Identifier
    requested_at: datetime


class ApprovalDecision(DomainRecord):
    approval_id: Identifier
    tenant_id: Identifier
    case_id: Identifier
    approval_type: Literal["scope", "containment", "notification", "closure"]
    decision: Literal["approved", "rejected"]
    rationale: Identifier
    requester_id: Identifier
    approver_id: Identifier
    case_version: NonNegativeVersion
    boundary_version: Identifier
    scope_version: NonNegativeVersion | None = None
    payload_version: Identifier | None = None
    policy_version: Identifier | None = None
    decided_at: datetime


class NotificationPacket(DomainRecord):
    packet_id: Identifier
    tenant_id: Identifier
    case_id: Identifier
    scope_id: Identifier
    scope_version: NonNegativeVersion
    payload_version: Identifier
    payload_hash: Identifier
    status: Literal["planned", "in_flight", "sent", "failed", "unknown"]
    recipient_ids: Annotated[tuple[Identifier, ...], Field(min_length=1)]
    created_at: datetime


class Acknowledgement(DomainRecord):
    acknowledgement_id: Identifier
    tenant_id: Identifier
    case_id: Identifier
    packet_id: Identifier
    recipient_id: Identifier
    status: Literal["verified", "outstanding", "rejected"]
    acknowledged_at: datetime | None = None


class LedgerEntry(DomainRecord):
    ledger_id: Identifier
    tenant_id: Identifier
    case_id: Identifier
    sequence: NonNegativeVersion
    entry_type: Identifier
    record_ids: Annotated[tuple[Identifier, ...], Field(min_length=1)]
    payload_hash: Identifier
    prior_entry_hash: Identifier | None = None
    created_at: datetime


class RecoveryState(DomainRecord):
    """An orthogonal pause which can only return to its originating phase."""

    status: Literal["needs_information", "failed_retryable", "blocked"]
    parent_phase: Literal[
        "signal_received",
        "scope_review",
        "provisional_containment",
        "action_review",
        "ack_monitoring",
        "effectiveness_check",
        "closed",
    ]
    return_phase: Literal[
        "signal_received",
        "scope_review",
        "provisional_containment",
        "action_review",
        "ack_monitoring",
        "effectiveness_check",
        "closed",
    ]
    reason_record_ids: Annotated[tuple[Identifier, ...], Field(min_length=1)]
    retry_attempt: NonNegativeVersion | None = None
    retry_limit: NonNegativeVersion | None = None


class IncidentState(DomainRecord):
    case: RecallCase
    scopes: tuple[AffectedScope, ...] = ()
    impacts: tuple[ImpactRecord, ...] = ()
    containment_actions: tuple[ContainmentAction, ...] = ()
    notification_packets: tuple[NotificationPacket, ...] = ()
    acknowledgements: tuple[Acknowledgement, ...] = ()
    approvals: tuple[ApprovalDecision, ...] = ()
    ledger: tuple[LedgerEntry, ...] = ()
    recovery: RecoveryState | None = None
    updated_at: datetime
