"""Strict, immutable records that make up an incident's operational truth."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

Identifier = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
RationaleText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=5)]
Sha256Hash = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^[a-fA-F0-9]{64}$")]
NonNegativeVersion = Annotated[int, Field(ge=0)]

Phase = Literal[
    "signal_received",
    "scope_review",
    "provisional_containment",
    "action_review",
    "ack_monitoring",
    "effectiveness_check",
    "closed",
]


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
    phase: Phase
    case_version: NonNegativeVersion
    source_record_ids: Annotated[tuple[Identifier, ...], Field(min_length=1)]
    created_at: datetime
    updated_at: datetime


class EvidenceSpan(DomainRecord):
    evidence_id: Identifier
    tenant_id: Identifier
    case_id: Identifier
    source_record_id: Identifier
    source_doc_hash: Sha256Hash
    doc_version: Identifier
    claim_type: Identifier
    start_offset: NonNegativeVersion
    end_offset: NonNegativeVersion
    captured_at: datetime

    @model_validator(mode="after")
    def validate_offset_range(self) -> Self:
        if self.end_offset <= self.start_offset:
            raise ValueError(f"end_offset ({self.end_offset}) must be strictly greater than start_offset ({self.start_offset})")
        return self


class AffectedScope(DomainRecord):
    scope_id: Identifier
    tenant_id: Identifier
    case_id: Identifier
    case_version: NonNegativeVersion
    scope_version: NonNegativeVersion
    status: Literal["proposed", "approved", "superseded"]
    affected_record_ids: tuple[Identifier, ...] = ()
    evidence_record_ids: Annotated[tuple[Identifier, ...], Field(min_length=1)]
    affected_quantity: NonNegativeQuantity
    created_at: datetime
    ingredient_lot: Identifier | None = None


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
    hold_expires_at: datetime | None = None
    idempotency_token: Identifier | None = None
    payload_hash: Identifier | None = None
    provider_reference: Identifier | None = None
    attempt: NonNegativeVersion = 0


Role = Literal["recall_coordinator", "qa", "customer_operations", "agent_service", "closure_authority"]


class ApprovalDecision(DomainRecord):
    kind: Literal["approval_decision"] = "approval_decision"
    approval_id: Identifier
    tenant_id: Identifier
    case_id: Identifier
    approval_type: Literal["scope", "containment", "notification", "closure", "release"]
    decision: Literal["approved", "rejected"]
    rationale: RationaleText
    requester_id: Identifier
    approver_id: Identifier
    approver_role: Role | None = None
    case_version: NonNegativeVersion
    boundary_version: Identifier
    scope_id: Identifier | None = None
    scope_version: NonNegativeVersion | None = None
    payload_version: Identifier | None = None
    policy_version: Identifier | None = None
    retest_doc_id: Identifier | None = None
    retest_doc_hash: Sha256Hash | None = None
    decided_at: datetime

    @model_validator(mode="after")
    def validate_release_evidence(self) -> Self:
        if self.approval_type == "release" and not (self.retest_doc_id and self.retest_doc_hash):
            raise ValueError("Release approval decision requires both retest_doc_id and verified 64-char hex retest_doc_hash")
        return self


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
    caller_id: Identifier | None = None
    recipient_contact: Identifier | None = None
    recipient_phone: Identifier | None = None
    attestation_notes: Identifier | None = None
    attestation_hash: Identifier | None = None
    acknowledged_at: datetime | None = None

    @model_validator(mode="after")
    def validate_verified_evidence(self) -> Self:
        if self.status == "verified" and not self.acknowledged_at:
            raise ValueError("Verified acknowledgement requires acknowledged_at timestamp")
        return self


class LedgerEntry(DomainRecord):
    ledger_id: Identifier
    tenant_id: Identifier
    case_id: Identifier
    sequence: NonNegativeVersion
    entry_type: Identifier
    record_ids: Annotated[tuple[Identifier, ...], Field(min_length=1)]
    payload_hash: Identifier
    prior_entry_hash: Identifier | None = None
    entry_hash: Identifier
    created_at: datetime


class RecoveryState(DomainRecord):
    """An orthogonal pause which can only return to its originating phase."""

    status: Literal["needs_information", "failed_retryable", "blocked"]
    parent_phase: Phase
    return_phase: Phase
    reason_record_ids: Annotated[tuple[Identifier, ...], Field(min_length=1)]
    retry_attempt: NonNegativeVersion | None = None
    retry_limit: NonNegativeVersion | None = None

    @model_validator(mode="after")
    def validate_phase_consistency(self) -> Self:
        if self.parent_phase != self.return_phase:
            raise ValueError(f"parent_phase ({self.parent_phase}) must match return_phase ({self.return_phase})")
        if self.parent_phase == "closed":
            raise ValueError("Recovery state cannot pause in or return to terminal 'closed' phase")
        return self


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

    @model_validator(mode="after")
    def enforce_tenant_case_coherence(self) -> Self:
        tenant_id = self.case.tenant_id
        case_id = self.case.case_id
        for s in self.scopes:
            if s.tenant_id != tenant_id or s.case_id != case_id:
                raise ValueError(f"Scope {s.scope_id} tenant/case mismatch with parent case ({tenant_id}/{case_id})")
        for a in self.containment_actions:
            if a.tenant_id != tenant_id or a.case_id != case_id:
                raise ValueError(f"Containment action {a.action_id} tenant/case mismatch with parent case ({tenant_id}/{case_id})")
        for app in self.approvals:
            if app.tenant_id != tenant_id or app.case_id != case_id:
                raise ValueError(f"Approval {app.approval_id} tenant/case mismatch with parent case ({tenant_id}/{case_id})")
        for ack in self.acknowledgements:
            if ack.tenant_id != tenant_id or ack.case_id != case_id:
                raise ValueError(f"Acknowledgement {ack.acknowledgement_id} tenant/case mismatch with parent case ({tenant_id}/{case_id})")
        for l in self.ledger:
            if l.tenant_id != tenant_id or l.case_id != case_id:
                raise ValueError(f"Ledger entry {l.ledger_id} tenant/case mismatch with parent case ({tenant_id}/{case_id})")
        return self
