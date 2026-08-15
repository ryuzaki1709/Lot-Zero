"""Standing policy decisions refuse incomplete or out-of-bound hold intents."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from lot_zero.domain.identifiers import ActionIntent
from lot_zero.domain.models import AffectedScope, IncidentState, RecallCase
from lot_zero.domain.policies import evaluate_hold_policy

NOW = datetime(2026, 8, 14, 12, tzinfo=UTC)
TENANT = "EVAL-TENANT-01"
CASE = "EVAL-CASE-01"
TARGETS = ("FP-100-L240814-A", "FP-100-L240814-B")


def state_with_affected_scope() -> IncidentState:
    return IncidentState(
        case=RecallCase(
            case_id=CASE,
            tenant_id=TENANT,
            phase="provisional_containment",
            case_version=3,
            source_record_ids=("LAB-SIGNAL-20260814-001",),
            created_at=NOW,
            updated_at=NOW,
        ),
        scopes=(
            AffectedScope(
                scope_id="SCOPE-EVAL-01",
                tenant_id=TENANT,
                case_id=CASE,
                case_version=3,
                scope_version=2,
                status="approved",
                affected_record_ids=TARGETS,
                evidence_record_ids=("LAB-SIGNAL-20260814-001",),
                affected_quantity=Decimal("200"),
                created_at=NOW,
            ),
        ),
        updated_at=NOW,
    )


def hold_intent(**overrides: object) -> ActionIntent:
    return ActionIntent.model_validate(
        {
            "tenant_id": TENANT,
            "case_id": CASE,
            "effect_kind": "provisional_hold",
            "scope_id": "SCOPE-EVAL-01",
            "scope_version": 2,
            "payload_version": "hold-payload-v1",
            "policy_version": "EVAL-HOLD-01",
            "target_record_ids": TARGETS,
            "payload_hash": "hold-payload-sha256",
            "quantity": Decimal("200"),
            "reversible": True,
            "expires_at": NOW + timedelta(minutes=30),
            **overrides,
        }
    )


def assert_inert_denial(decision, code: str) -> None:
    assert decision.allowed is False
    assert decision.code == code
    assert decision.requested_effects == ()
    assert decision.events == ()


def test_authored_hold_policy_allows_only_the_complete_golden_hold() -> None:
    decision = evaluate_hold_policy(hold_intent(), state_with_affected_scope(), NOW)

    assert decision.allowed is True
    assert decision.code == "ALLOWED"
    assert decision.requested_effects == (hold_intent(),)


@pytest.mark.parametrize(
    ("overrides", "code"),
    (
        ({"policy_version": "POLICY-OTHER"}, "POLICY_NOT_ALLOWED"),
        ({"tenant_id": "OTHER-TENANT"}, "TENANT_MISMATCH"),
        ({"case_id": "OTHER-CASE"}, "CASE_MISMATCH"),
        ({"effect_kind": "release_hold"}, "EFFECT_KIND_NOT_ALLOWED"),
        ({"target_record_ids": ("FP-100-ADJ",)}, "TARGET_NOT_AFFECTED"),
        ({"quantity": Decimal("201")}, "QUANTITY_EXCEEDS_POLICY"),
        ({"reversible": False}, "ACTION_NOT_REVERSIBLE"),
        ({"expires_at": NOW + timedelta(minutes=29)}, "EXPIRY_NOT_AUTHORED"),
        ({"expires_at": NOW + timedelta(minutes=31)}, "EXPIRY_NOT_AUTHORED"),
        ({"quantity": None}, "MISSING_QUANTITY"),
        ({"expires_at": None}, "MISSING_EXPIRY"),
        ({"reversible": None}, "MISSING_REVERSIBILITY"),
    ),
)
def test_hold_policy_denials_are_inert(overrides: dict[str, object], code: str) -> None:
    decision = evaluate_hold_policy(hold_intent(**overrides), state_with_affected_scope(), NOW)

    assert_inert_denial(decision, code)


def test_hold_policy_refuses_an_expired_now() -> None:
    decision = evaluate_hold_policy(
        hold_intent(), state_with_affected_scope(), NOW + timedelta(minutes=31)
    )

    assert_inert_denial(decision, "ACTION_EXPIRED")
