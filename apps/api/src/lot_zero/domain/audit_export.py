"""Tamper-evident audit bundle export with cryptographic hash chaining over the event stream."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel

from .identifiers import canonical_sha256


class AuditExportEventItem(BaseModel):
    """One tamper-evident event entry in the audit chain."""

    sequence: int
    stream_version: int
    event_id: str
    event_type: str
    occurred_at: str
    payload: dict[str, Any]
    payload_hash: str
    prior_entry_hash: str | None
    entry_hash: str


class AuditExportBundle(BaseModel):
    """Complete, self-verifying, tamper-evident audit export for regulatory compliance."""

    export_id: str
    tenant_id: str
    case_id: str
    exported_at: str
    exported_by_principal_id: str
    event_count: int
    events: list[AuditExportEventItem]
    top_level_digest: str


def compute_audit_entry_hash(
    sequence: int,
    event_type: str,
    payload_hash: str,
    prior_entry_hash: str | None,
    occurred_at: str,
) -> str:
    """Compute deterministic SHA-256 hash witnessing an audit entry and its chain linkage."""
    raw = f"{sequence}:{event_type}:{payload_hash}:{prior_entry_hash or ''}:{occurred_at}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def compute_top_level_digest(
    tenant_id: str,
    case_id: str,
    event_count: int,
    final_entry_hash: str | None,
) -> str:
    """Compute top-level cryptographic root digest witnessing the entire export bundle."""
    raw = f"{tenant_id}:{case_id}:{event_count}:{final_entry_hash or 'GENESIS'}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def generate_audit_export(
    conn: sqlite3.Connection,
    tenant_id: str,
    case_id: str,
    exported_by_principal_id: str,
) -> AuditExportBundle | None:
    """Export the ordered event stream for a case as a signed, hash-chained audit bundle.
    
    Scoped strictly by tenant_id and case_id. Returns None if case does not exist.
    """
    cursor = conn.execute(
        """
        SELECT stream_version, event_type, payload, occurred_at
        FROM incident_events
        WHERE tenant_id = ? AND case_id = ?
        ORDER BY stream_version ASC
        """,
        (tenant_id, case_id),
    )
    rows = cursor.fetchall()
    if not rows:
        return None

    now_iso = datetime.now(UTC).isoformat()
    export_id = f"AUDIT-EXPORT-{case_id}-{int(datetime.now(UTC).timestamp())}"
    event_items: list[AuditExportEventItem] = []
    prior_entry_hash: str | None = None

    for idx, row in enumerate(rows, start=1):
        stream_version = int(row[0])
        event_type = str(row[1])
        payload_raw = str(row[2])
        occurred_at = str(row[3])

        try:
            payload_dict = json.loads(payload_raw)
        except Exception:
            payload_dict = {"raw": payload_raw}

        # Canonical SHA-256 hash of the event payload
        payload_hash = canonical_sha256(payload_dict)
        event_id = payload_dict.get("event_id", payload_dict.get("approval_id", f"EVT-{stream_version}"))

        entry_hash = compute_audit_entry_hash(
            sequence=idx,
            event_type=event_type,
            payload_hash=payload_hash,
            prior_entry_hash=prior_entry_hash,
            occurred_at=occurred_at,
        )

        item = AuditExportEventItem(
            sequence=idx,
            stream_version=stream_version,
            event_id=event_id,
            event_type=event_type,
            occurred_at=occurred_at,
            payload=payload_dict,
            payload_hash=payload_hash,
            prior_entry_hash=prior_entry_hash,
            entry_hash=entry_hash,
        )
        event_items.append(item)
        prior_entry_hash = entry_hash

    top_level_digest = compute_top_level_digest(
        tenant_id=tenant_id,
        case_id=case_id,
        event_count=len(event_items),
        final_entry_hash=prior_entry_hash,
    )

    return AuditExportBundle(
        export_id=export_id,
        tenant_id=tenant_id,
        case_id=case_id,
        exported_at=now_iso,
        exported_by_principal_id=exported_by_principal_id,
        event_count=len(event_items),
        events=event_items,
        top_level_digest=top_level_digest,
    )


def verify_audit_bundle(bundle_data: dict[str, Any] | AuditExportBundle) -> tuple[bool, str | None]:
    """Verify cryptographic integrity of an audit export bundle: payload hashes, hash chain, and root digest."""
    bundle = (
        bundle_data
        if isinstance(bundle_data, AuditExportBundle)
        else AuditExportBundle.model_validate(bundle_data)
    )

    if not bundle.events:
        expected_root = compute_top_level_digest(bundle.tenant_id, bundle.case_id, 0, None)
        if bundle.top_level_digest != expected_root:
            return False, "Top-level root digest mismatch on empty bundle"
        return True, None

    expected_prior_hash: str | None = None

    for idx, item in enumerate(bundle.events, start=1):
        if item.sequence != idx:
            return False, f"Sequence discontinuity at index {idx}: found {item.sequence}"

        # 1. Verify payload hash
        recomputed_payload_hash = canonical_sha256(item.payload)
        if item.payload_hash != recomputed_payload_hash:
            return (
                False,
                f"Payload hash tampering detected at sequence {idx} (event {item.event_id}): "
                f"recorded {item.payload_hash} != computed {recomputed_payload_hash}",
            )

        # 2. Verify prior entry hash linkage
        if item.prior_entry_hash != expected_prior_hash:
            return (
                False,
                f"Broken hash chain link at sequence {idx}: "
                f"recorded prior {item.prior_entry_hash} != expected {expected_prior_hash}",
            )

        # 3. Verify entry hash
        recomputed_entry_hash = compute_audit_entry_hash(
            sequence=item.sequence,
            event_type=item.event_type,
            payload_hash=item.payload_hash,
            prior_entry_hash=item.prior_entry_hash,
            occurred_at=item.occurred_at,
        )
        if item.entry_hash != recomputed_entry_hash:
            return (
                False,
                f"Entry hash tampering detected at sequence {idx}: "
                f"recorded {item.entry_hash} != computed {recomputed_entry_hash}",
            )

        expected_prior_hash = item.entry_hash

    # 4. Verify top-level root digest
    expected_top_digest = compute_top_level_digest(
        tenant_id=bundle.tenant_id,
        case_id=bundle.case_id,
        event_count=len(bundle.events),
        final_entry_hash=expected_prior_hash,
    )
    if bundle.top_level_digest != expected_top_digest:
        return (
            False,
            f"Top-level root digest mismatch: recorded {bundle.top_level_digest} != computed {expected_top_digest}",
        )

    return True, None
