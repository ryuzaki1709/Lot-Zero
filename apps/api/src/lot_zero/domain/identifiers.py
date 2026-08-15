"""Canonical hashes and stable effect keys for safe-retry orchestration."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field

from .models import DomainRecord, Identifier, NonNegativeVersion

type JsonScalar = None | bool | int | float | str
type JsonValue = (
    JsonScalar
    | Decimal
    | datetime
    | BaseModel
    | Sequence[JsonValue]
    | Mapping[str, JsonValue]
)


class ActionIntent(DomainRecord):
    """Stable semantics of one external effect, excluding delivery mechanics."""

    tenant_id: Identifier
    case_id: Identifier
    effect_kind: Identifier
    scope_id: Identifier
    scope_version: NonNegativeVersion
    payload_version: Identifier
    policy_version: Identifier
    target_record_ids: Annotated[tuple[Identifier, ...], Field(min_length=1)]
    payload_hash: Identifier


def _canonical_decimal(value: Decimal) -> dict[str, str]:
    if not value.is_finite():
        raise ValueError("Decimal values must be finite")
    normalized = value.normalize()
    rendered = format(normalized, "f")
    if rendered == "-0":
        rendered = "0"
    return {"$lot_zero_type": "decimal", "value": rendered}


def _canonical_datetime(value: datetime) -> dict[str, str]:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime values must be timezone-aware")
    rendered = value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    return {"$lot_zero_type": "datetime", "value": rendered}


def _canonicalize(value: JsonValue) -> object:
    if isinstance(value, BaseModel):
        return _canonicalize(value.model_dump(mode="python"))
    if isinstance(value, Decimal):
        return _canonical_decimal(value)
    if isinstance(value, datetime):
        return _canonical_datetime(value)
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("float values must be finite")
        return value
    if isinstance(value, Mapping):
        canonical_mapping: dict[str, object] = {}
        for key, nested_value in value.items():
            if not isinstance(key, str):
                raise TypeError("JSON object keys must be strings")
            canonical_mapping[key] = _canonicalize(nested_value)
        return canonical_mapping
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_canonicalize(item) for item in value]
    raise TypeError(f"unsupported canonical JSON value: {type(value).__name__}")


def canonical_sha256(value: JsonValue) -> str:
    """Return the SHA-256 of typed, sorted, compact UTF-8 canonical JSON."""

    canonical_json = json.dumps(
        _canonicalize(value),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    )
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def action_key(intent: ActionIntent) -> str:
    """Create a stable key for later retry/reconciliation logic, not exactly-once delivery."""

    return canonical_sha256(intent)
