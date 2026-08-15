from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from lot_zero.domain.identifiers import ActionIntent, action_key, canonical_sha256


def intent_dict() -> dict[str, object]:
    return {
        "tenant_id": "EVAL-TENANT-01",
        "case_id": "CASE-001",
        "effect_kind": "provisional_hold",
        "scope_id": "SCOPE-001",
        "scope_version": 1,
        "payload_version": "payload-v1",
        "policy_version": "policy-v1",
        "target_record_ids": ("FP-100-L240814-A", "FP-100-L240814-B"),
        "payload_hash": "payload-sha256",
    }


def test_action_key_ignores_dictionary_order_and_changes_for_effect_semantics():
    first = ActionIntent(**intent_dict())
    reordered = ActionIntent(**dict(reversed(intent_dict().items())))
    changed = ActionIntent(**{**intent_dict(), "payload_version": "payload-v2"})

    assert action_key(first) == action_key(reordered)
    assert action_key(first) != action_key(changed)


def test_transport_delivery_and_retry_metadata_cannot_change_action_key():
    intent = ActionIntent(**intent_dict())
    assert action_key(intent) == action_key(intent)

    with pytest.raises(ValidationError):
        ActionIntent(**intent_dict(), pubsub_delivery_id="delivery-1", retry_count=2)


def test_canonical_hash_is_order_independent_and_preserves_decimal_datetime_types():
    instant = datetime(2026, 8, 14, 12, tzinfo=UTC)
    equivalent_offset = instant.astimezone(timezone(timedelta(hours=5, minutes=30)))
    value = {"when": instant, "quantity": Decimal("1.00"), "tags": ["a", 1]}
    reordered = {"tags": ["a", 1], "quantity": Decimal("1"), "when": equivalent_offset}

    assert canonical_sha256(value) == canonical_sha256(reordered)
    assert canonical_sha256(Decimal("1")) != canonical_sha256("1")


def test_canonical_hash_rejects_naive_and_nonfinite_numbers():
    with pytest.raises(ValueError, match="timezone-aware"):
        canonical_sha256(datetime(2026, 8, 14, 12))
    with pytest.raises(ValueError, match="finite"):
        canonical_sha256(Decimal("NaN"))
