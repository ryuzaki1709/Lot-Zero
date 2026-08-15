"""Seed demo incident cases and events into SQLite event store for local evaluation."""

import os
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "apps" / "api" / "src"))

from lot_zero.adapters.sqlite_repository import SqliteIncidentRepository
from lot_zero.domain.events import (
    AcknowledgementRecordedEvent,
    ApprovalDecision,
    ContainmentReleasedEvent,
    ContainmentRequestedEvent,
    NotificationRequestedEvent,
    ScopeProposedEvent,
    TransitionEvent,
)
from lot_zero.domain.models import IncidentState, RecallCase

NOW = datetime(2026, 8, 14, 12, 0, 0, tzinfo=UTC)
TENANT_ID = "EVAL-TENANT-01"
DB_PATH = os.environ.get("LOT_ZERO_DB_PATH", str(Path(__file__).resolve().parent.parent / "apps" / "api" / "lot_zero.db"))


def initial_state(tenant_id: str, case_id: str) -> IncidentState:
    return IncidentState(
        case=RecallCase(
            case_id=case_id,
            tenant_id=tenant_id,
            phase="signal_received",
            case_version=0,
            source_record_ids=("LAB-SEED-01",),
            created_at=NOW,
            updated_at=NOW,
        ),
        updated_at=NOW,
    )


async def seed():
    print(f"Seeding demo cases into: {DB_PATH}")
    repo = SqliteIncidentRepository(db_path=DB_PATH, initial_state_factory=initial_state)

    # 1. CASE-SALMONELLA-4417 (Active Hold)
    ev_c1_1 = ScopeProposedEvent(
        event_id="EVT-SEED-C1-01",
        tenant_id=TENANT_ID,
        case_id="CASE-SALMONELLA-4417",
        actor_id="RECALL-COORD-01",
        case_version=0,
        scope_id="SCOPE-SAL-01",
        scope_version=1,
        affected_record_ids=("FP-100-L240814-A", "FP-100-L240814-B"),
        affected_quantity=Decimal("200"),
        evidence_record_ids=("LAB-SAL-01", "LAB-SAL-02"),
        occurred_at=NOW - timedelta(hours=2),
    )
    ev_c1_2 = ContainmentRequestedEvent(
        event_id="EVT-SEED-C1-02",
        tenant_id=TENANT_ID,
        case_id="CASE-SALMONELLA-4417",
        actor_id="RECALL-COORD-01",
        case_version=1,
        scope_id="SCOPE-SAL-01",
        scope_version=1,
        action_id="ACT-HOLD-SAL-01",
        policy_version="EVAL-HOLD-01",
        target_record_ids=("FP-100-L240814-A", "FP-100-L240814-B"),
        occurred_at=NOW - timedelta(hours=2),
    )
    await repo.append("CASE-SALMONELLA-4417", expected_version=0, events=[ev_c1_1, ev_c1_2], tenant_id=TENANT_ID)

    # 2. CASE-LISTERIA-9921 (Pending QA Scope Approval)
    ev_c2_1 = ScopeProposedEvent(
        event_id="EVT-SEED-C2-01",
        tenant_id=TENANT_ID,
        case_id="CASE-LISTERIA-9921",
        actor_id="RECALL-COORD-01",
        case_version=0,
        scope_id="SCOPE-LIS-01",
        scope_version=1,
        affected_record_ids=("FP-200-L240815-A",),
        affected_quantity=Decimal("350"),
        evidence_record_ids=("LAB-LIS-01",),
        occurred_at=NOW - timedelta(hours=1),
    )
    ev_c2_2 = TransitionEvent(
        event_id="EVT-SEED-C2-02",
        tenant_id=TENANT_ID,
        case_id="CASE-LISTERIA-9921",
        case_version=1,
        kind="advance",
        target_phase="scope_review",
        occurred_at=NOW - timedelta(hours=1),
    )
    await repo.append("CASE-LISTERIA-9921", expected_version=0, events=[ev_c2_1, ev_c2_2], tenant_id=TENANT_ID)

    # 3. CASE-ALLERGEN-102 (Blocked by Consignee Refusal)
    ev_c3_1 = ScopeProposedEvent(
        event_id="EVT-SEED-C3-01",
        tenant_id=TENANT_ID,
        case_id="CASE-ALLERGEN-102",
        actor_id="RECALL-COORD-01",
        case_version=0,
        scope_id="SCOPE-ALL-01",
        scope_version=1,
        affected_record_ids=("FP-300-L240810-C",),
        affected_quantity=Decimal("80"),
        evidence_record_ids=("LAB-ALL-01",),
        occurred_at=NOW - timedelta(days=1),
    )
    ev_c3_2 = AcknowledgementRecordedEvent(
        event_id="EVT-SEED-C3-02",
        tenant_id=TENANT_ID,
        case_id="CASE-ALLERGEN-102",
        actor_id="OPS-01",
        case_version=1,
        packet_id="PKT-ALL-01",
        acknowledgement_id="ACK-REFUSED-DISTRIB-9",
        recipient_id="RECIPIENT-009",
        acknowledgement_status="rejected",
        occurred_at=NOW - timedelta(hours=12),
    )
    await repo.append("CASE-ALLERGEN-102", expected_version=0, events=[ev_c3_1, ev_c3_2], tenant_id=TENANT_ID)

    # 4. CASE-BENZENE-CLOSED (Closed with Dual-Signature Release)
    ev_c4_1 = ScopeProposedEvent(
        event_id="EVT-SEED-C4-01",
        tenant_id=TENANT_ID,
        case_id="CASE-BENZENE-CLOSED",
        actor_id="RECALL-COORD-01",
        case_version=0,
        scope_id="SCOPE-BNZ-01",
        scope_version=1,
        affected_record_ids=("FP-400-L240801-A",),
        affected_quantity=Decimal("50"),
        evidence_record_ids=("LAB-BNZ-01",),
        occurred_at=NOW - timedelta(days=3),
    )
    ev_c4_2 = ContainmentReleasedEvent(
        event_id="EVT-SEED-C4-02",
        tenant_id=TENANT_ID,
        case_id="CASE-BENZENE-CLOSED",
        actor_id="QA-LEAD-01",
        case_version=1,
        action_id="ACT-BNZ-01",
        scope_id="SCOPE-BNZ-01",
        retest_doc_id="LAB-RETEST-CLEAN-01",
        retest_doc_hash="a" * 64,
        occurred_at=NOW - timedelta(days=2),
    )
    ev_c4_3 = TransitionEvent(
        event_id="EVT-SEED-C4-03",
        tenant_id=TENANT_ID,
        case_id="CASE-BENZENE-CLOSED",
        case_version=2,
        kind="advance",
        target_phase="closed",
        occurred_at=NOW - timedelta(days=1),
    )
    await repo.append("CASE-BENZENE-CLOSED", expected_version=0, events=[ev_c4_1, ev_c4_2, ev_c4_3], tenant_id=TENANT_ID)

    repo.close()
    print("Demo seed complete! 4 cases populated in SQLite.")


if __name__ == "__main__":
    import asyncio
    asyncio.run(seed())
