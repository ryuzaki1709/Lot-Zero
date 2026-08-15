from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from lot_zero.domain.commands import Command, RequestContainmentCommand
from lot_zero.domain.events import Event, ScopeProposedEvent
from lot_zero.domain.models import AffectedScope, RecallCase


def valid_case() -> dict[str, object]:
    return {
        "case_id": "CASE-001",
        "tenant_id": "EVAL-TENANT-01",
        "phase": "signal_received",
        "case_version": 1,
        "source_record_ids": ("LAB-SIGNAL-20260814-001",),
        "created_at": datetime(2026, 8, 14, 12, tzinfo=UTC),
        "updated_at": datetime(2026, 8, 14, 12, tzinfo=UTC),
    }


def test_naive_timestamp_and_unknown_field_are_rejected():
    with pytest.raises(ValidationError):
        RecallCase.model_validate({**valid_case(), "updated_at": "2026-08-14T12:00:00", "fake": 1})


def test_records_are_frozen_and_reject_negative_quantities():
    case = RecallCase.model_validate(valid_case())
    with pytest.raises(ValidationError):
        case.phase = "closed"

    with pytest.raises(ValidationError):
        AffectedScope(
            scope_id="SCOPE-001",
            tenant_id="EVAL-TENANT-01",
            case_id="CASE-001",
            case_version=1,
            scope_version=1,
            status="proposed",
            affected_record_ids=("FP-100-L240814-A",),
            evidence_record_ids=("LAB-SIGNAL-20260814-001",),
            affected_quantity=Decimal("-0.01"),
            created_at=datetime(2026, 8, 14, 12, tzinfo=UTC),
        )


def test_equal_decimal_quantities_have_one_persisted_serialization():
    shared_scope = {
        "scope_id": "SCOPE-001",
        "tenant_id": "EVAL-TENANT-01",
        "case_id": "CASE-001",
        "case_version": 1,
        "scope_version": 1,
        "status": "proposed",
        "affected_record_ids": ("FP-100-L240814-A",),
        "evidence_record_ids": ("LAB-SIGNAL-20260814-001",),
        "created_at": datetime(2026, 8, 14, 12, tzinfo=UTC),
    }
    formatted_quantity = AffectedScope(**shared_scope, affected_quantity=Decimal("1.00"))
    whole_quantity = AffectedScope(**shared_scope, affected_quantity=Decimal("1"))

    assert formatted_quantity.model_dump_json() == whole_quantity.model_dump_json()


def test_quantity_normalization_keeps_small_values_and_strips_extra_zeroes():
    shared_scope = {
        "scope_id": "SCOPE-001",
        "tenant_id": "EVAL-TENANT-01",
        "case_id": "CASE-001",
        "case_version": 1,
        "scope_version": 1,
        "status": "proposed",
        "affected_record_ids": ("FP-100-L240814-A",),
        "evidence_record_ids": ("LAB-SIGNAL-20260814-001",),
        "created_at": datetime(2026, 8, 14, 12, tzinfo=UTC),
    }

    tiny_quantity = AffectedScope(**shared_scope, affected_quantity=Decimal("0.0000001"))
    formatted_quantity = AffectedScope(**shared_scope, affected_quantity=Decimal("1.0000000"))
    whole_quantity = AffectedScope(**shared_scope, affected_quantity=Decimal("1"))

    assert tiny_quantity.affected_quantity == Decimal("0.0000001")
    assert formatted_quantity.model_dump_json() == whole_quantity.model_dump_json()


@pytest.mark.parametrize(
    ("first_quantity", "equivalent_quantity"),
    (
        (Decimal("1e100000000"), Decimal("10e99999999")),
        (Decimal("1e-100000000"), Decimal("10e-100000001")),
    ),
)
def test_quantity_normalization_keeps_huge_exponents_compact_and_deterministic(
    first_quantity, equivalent_quantity
):
    shared_scope = {
        "scope_id": "SCOPE-001",
        "tenant_id": "EVAL-TENANT-01",
        "case_id": "CASE-001",
        "case_version": 1,
        "scope_version": 1,
        "status": "proposed",
        "affected_record_ids": ("FP-100-L240814-A",),
        "evidence_record_ids": ("LAB-SIGNAL-20260814-001",),
        "created_at": datetime(2026, 8, 14, 12, tzinfo=UTC),
    }
    first = AffectedScope(**shared_scope, affected_quantity=first_quantity)
    equivalent = AffectedScope(**shared_scope, affected_quantity=equivalent_quantity)

    assert first.affected_quantity == equivalent.affected_quantity
    assert first.model_dump_json() == equivalent.model_dump_json()
    assert len(first.model_dump_json()) < 400


def test_command_and_event_unions_are_closed_by_kind():
    command = Command.validate_python(
        {
            "kind": "request_containment",
            "command_id": "CMD-001",
            "tenant_id": "EVAL-TENANT-01",
            "case_id": "CASE-001",
            "actor_id": "ACTOR-001",
            "scope_id": "SCOPE-001",
            "case_version": 1,
            "scope_version": 1,
            "policy_version": "policy-v1",
            "action_type": "provisional_hold",
            "target_record_ids": ["FP-100-L240814-A"],
        }
    )
    assert isinstance(command, RequestContainmentCommand)

    event = Event.validate_python(
        {
            "kind": "scope_proposed",
            "event_id": "EVENT-001",
            "tenant_id": "EVAL-TENANT-01",
            "case_id": "CASE-001",
            "actor_id": "ACTOR-001",
            "case_version": 1,
            "scope_version": 1,
            "scope_id": "SCOPE-001",
            "evidence_record_ids": ["LAB-SIGNAL-20260814-001"],
            "occurred_at": "2026-08-14T12:00:00Z",
        }
    )
    assert isinstance(event, ScopeProposedEvent)

    with pytest.raises(ValidationError):
        Command.validate_python({"kind": "invented"})
    with pytest.raises(ValidationError):
        Event.validate_python({"kind": "invented"})


def test_evidence_span_document_binding_and_offset_invariants():
    from lot_zero.domain.models import EvidenceSpan

    now = datetime(2026, 8, 14, 12, tzinfo=UTC)
    valid_hash = "a" * 64

    # Valid span
    span = EvidenceSpan(
        evidence_id="EVID-01",
        tenant_id="EVAL-TENANT-01",
        case_id="CASE-001",
        source_record_id="LAB-SIGNAL-01",
        source_doc_hash=valid_hash,
        doc_version="v1.0",
        claim_type="contaminated_lot",
        start_offset=10,
        end_offset=50,
        captured_at=now,
    )
    assert span.end_offset > span.start_offset

    # Inverted offsets rejected
    with pytest.raises(ValidationError):
        EvidenceSpan(
            evidence_id="EVID-01",
            tenant_id="EVAL-TENANT-01",
            case_id="CASE-001",
            source_record_id="LAB-SIGNAL-01",
            source_doc_hash=valid_hash,
            doc_version="v1.0",
            claim_type="contaminated_lot",
            start_offset=50,
            end_offset=10,
            captured_at=now,
        )

    # Invalid SHA-256 hash rejected
    with pytest.raises(ValidationError):
        EvidenceSpan(
            evidence_id="EVID-01",
            tenant_id="EVAL-TENANT-01",
            case_id="CASE-001",
            source_record_id="LAB-SIGNAL-01",
            source_doc_hash="not-a-sha256",
            doc_version="v1.0",
            claim_type="contaminated_lot",
            start_offset=10,
            end_offset=50,
            captured_at=now,
        )


def test_ledger_cryptographic_chain_and_tamper_detection():
    from lot_zero.domain.errors import InvariantViolation
    from lot_zero.domain.ledger import append_ledger_entry, verify_ledger

    now = datetime(2026, 8, 14, 12, tzinfo=UTC)
    ledger = ()

    ledger = append_ledger_entry(
        ledger,
        ledger_id="LEDGER-001",
        tenant_id="EVAL-TENANT-01",
        case_id="CASE-001",
        entry_type="SCOPE_PROPOSED",
        record_ids=("SCOPE-001",),
        payload_hash="hash-1",
        created_at=now,
    )
    ledger = append_ledger_entry(
        ledger,
        ledger_id="LEDGER-002",
        tenant_id="EVAL-TENANT-01",
        case_id="CASE-001",
        entry_type="CONTAINMENT_REQUESTED",
        record_ids=("ACT-001",),
        payload_hash="hash-2",
        created_at=now,
    )

    # 1. Clean ledger verification passes
    assert verify_ledger(ledger) is True
    assert len(ledger) == 2
    assert ledger[1].prior_entry_hash == ledger[0].entry_hash

    # 2. Tampered entry_type detected
    tampered_entry = ledger[0].model_copy(update={"entry_type": "TAMPERED_ENTRY_TYPE"})
    tampered_ledger = (tampered_entry, ledger[1])
    with pytest.raises(InvariantViolation, match="Ledger entry hash tampering detected"):
        verify_ledger(tampered_ledger)

    # 3. Broken hash chain detected
    tampered_chain = (ledger[0], ledger[1].model_copy(update={"prior_entry_hash": "broken_hash"}))
    with pytest.raises(InvariantViolation, match="Ledger hash-chain break"):
        verify_ledger(tampered_chain)

