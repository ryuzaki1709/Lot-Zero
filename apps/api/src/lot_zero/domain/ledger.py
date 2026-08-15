"""Append-only cryptographic hash-chain ledger for incident provenance."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from .errors import InvariantViolation
from .identifiers import canonical_sha256
from .models import Identifier, LedgerEntry


def compute_entry_hash(
    *,
    ledger_id: str,
    tenant_id: str,
    case_id: str,
    sequence: int,
    entry_type: str,
    record_ids: Sequence[str],
    payload_hash: str,
    prior_entry_hash: str | None,
    created_at: datetime,
) -> str:
    """Deterministic SHA-256 for a single ledger record covering all metadata and prior link."""
    payload = {
        "ledger_id": ledger_id,
        "tenant_id": tenant_id,
        "case_id": case_id,
        "sequence": sequence,
        "entry_type": entry_type,
        "record_ids": sorted(record_ids),
        "payload_hash": payload_hash,
        "prior_entry_hash": prior_entry_hash or "",
        "created_at": created_at.isoformat(),
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
    created_at: datetime,
) -> tuple[LedgerEntry, ...]:
    """Append a new ledger entry, computing entry_hash and establishing the verified hash chain."""
    prior_entry = ledger[-1] if ledger else None
    sequence = (prior_entry.sequence + 1) if prior_entry else 1
    prior_hash = prior_entry.entry_hash if prior_entry else None

    entry_hash = compute_entry_hash(
        ledger_id=ledger_id,
        tenant_id=tenant_id,
        case_id=case_id,
        sequence=sequence,
        entry_type=entry_type,
        record_ids=record_ids,
        payload_hash=payload_hash,
        prior_entry_hash=prior_hash,
        created_at=created_at,
    )

    entry = LedgerEntry(
        ledger_id=ledger_id,
        tenant_id=tenant_id,
        case_id=case_id,
        sequence=sequence,
        entry_type=entry_type,
        record_ids=tuple(sorted(record_ids)),
        payload_hash=payload_hash,
        prior_entry_hash=prior_hash,
        entry_hash=entry_hash,
        created_at=created_at,
    )
    return (*ledger, entry)


def verify_ledger(ledger: Sequence[LedgerEntry]) -> bool:
    """Verify cryptographic integrity, ordering, and unbroken hash-chain across all entries."""
    if not ledger:
        return True

    expected_prior_hash: str | None = None
    for idx, entry in enumerate(ledger):
        expected_seq = idx + 1
        if entry.sequence != expected_seq:
            raise InvariantViolation(
                f"Ledger sequence discontinuity at index {idx}: expected {expected_seq}, got {entry.sequence}"
            )
        if entry.prior_entry_hash != expected_prior_hash:
            raise InvariantViolation(
                f"Ledger hash-chain break at sequence {entry.sequence}: "
                f"expected prior_entry_hash '{expected_prior_hash}', got '{entry.prior_entry_hash}'"
            )
        recomputed_hash = compute_entry_hash(
            ledger_id=entry.ledger_id,
            tenant_id=entry.tenant_id,
            case_id=entry.case_id,
            sequence=entry.sequence,
            entry_type=entry.entry_type,
            record_ids=entry.record_ids,
            payload_hash=entry.payload_hash,
            prior_entry_hash=entry.prior_entry_hash,
            created_at=entry.created_at,
        )
        if entry.entry_hash != recomputed_hash:
            raise InvariantViolation(
                f"Ledger entry hash tampering detected at sequence {entry.sequence}: "
                f"recorded '{entry.entry_hash}', recomputed '{recomputed_hash}'"
            )
        expected_prior_hash = entry.entry_hash

    return True
