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
        "phase": "signal_review",
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
