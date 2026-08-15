"""Append-only cryptographic hash-chain ledger for incident provenance."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from .identifiers import canonical_sha256
from .models import Identifier, LedgerEntry


def compute_entry_hash(
    tenant_id: str,
    case_id: str,
    sequence: int,
    entry_type: str,
    record_ids: Sequence[str],
    payload_hash: str,
    prior_entry_hash: str | None,
) -> str:
    """Deterministic SHA-256 for a single ledger record linked to prior hash."""
    payload = {
        "tenant_id": tenant_id,
        "case_id": case_id,
        "sequence": sequence,
        "entry_type": entry_type,
        "record_ids": sorted(record_ids),
        "payload_hash": payload_hash,
        "prior_entry_hash": prior_entry_hash or "",
    }
    return canonical_sha256(payload)


def append_ledger_entry(
    ledger: Sequence[LedgerEntry],
    *,
    ledger_id: Identifier,
    tenant_id: Identifier,
    case_id: Identifier,
    entry_type: Identifier,
    record_ids: Sequence[Identifier],
    payload_hash: Identifier,
    created_at: datetime | None = None,
) -> tuple[LedgerEntry, ...]:
    """Append a new ledger entry, verifying and establishing the hash chain."""
    prior_entry = ledger[-1] if ledger else None
    sequence = (prior_entry.sequence + 1) if prior_entry else 1
    prior_hash = prior_entry.payload_hash if prior_entry else None
    now = created_at or datetime.now(UTC)

    entry = LedgerEntry(
        ledger_id=ledger_id,
        tenant_id=tenant_id,
        case_id=case_id,
        sequence=sequence,
        entry_type=entry_type,
        record_ids=tuple(sorted(record_ids)),
        payload_hash=payload_hash,
        prior_entry_hash=prior_hash,
        created_at=now,
    )
    return (*ledger, entry)
