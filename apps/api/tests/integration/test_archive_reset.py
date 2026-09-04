"""Integration tests for transactional, auditable reset and tenant isolation."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from lot_zero.adapters.sqlite_repository import SqliteIncidentRepository
from lot_zero.domain.events import ScopeProposedEvent

NOW = datetime(2026, 8, 14, 12, tzinfo=UTC)


@pytest.mark.anyio
async def test_archive_and_reset_atomicity_and_journaling(tmp_path):
    db_file = str(tmp_path / "test_reset.db")
    repo = SqliteIncidentRepository(db_file)

    t1 = "TENANT-01"
    c1 = "CASE-01"
    t2 = "TENANT-02"
    c2 = "CASE-02"

    ev1 = ScopeProposedEvent(
        event_id="EVT-01",
        tenant_id=t1,
        case_id=c1,
        actor_id="COORD-01",
        case_version=0,
        scope_id="SCOPE-01",
        scope_version=1,
        affected_record_ids=("REC-1",),
        affected_quantity=Decimal("100"),
        evidence_record_ids=("EVID-1",),
        occurred_at=NOW,
    )
    await repo.append(c1, 0, [ev1], tenant_id=t1)

    ev2 = ScopeProposedEvent(
        event_id="EVT-02",
        tenant_id=t2,
        case_id=c2,
        actor_id="COORD-02",
        case_version=0,
        scope_id="SCOPE-02",
        scope_version=1,
        affected_record_ids=("REC-2",),
        affected_quantity=Decimal("200"),
        evidence_record_ids=("EVID-2",),
        occurred_at=NOW,
    )
    await repo.append(c2, 0, [ev2], tenant_id=t2)

    # Verify initial state
    events_t1 = await repo.get_events(c1, tenant_id=t1)
    events_t2 = await repo.get_events(c2, tenant_id=t2)
    assert len(events_t1) == 1
    assert len(events_t2) == 1

    # Perform archive and reset on TENANT-01, CASE-01
    count = await repo.archive_and_reset(t1, c1, reset_by_principal_id="ADMIN-01")
    assert count == 1

    # Active stream for T1/C1 must be 0
    events_t1_after = await repo.get_events(c1, tenant_id=t1)
    assert len(events_t1_after) == 0

    # Active stream for T2/C2 must be untouched (1 event)
    events_t2_after = await repo.get_events(c2, tenant_id=t2)
    assert len(events_t2_after) == 1

    # Check database tables directly: archived_incident_events & evaluation_reset_journal
    with repo._conn:
        cur = repo._conn.execute(
            "SELECT COUNT(*) FROM archived_incident_events WHERE tenant_id = ? AND case_id = ?",
            (t1, c1),
        )
        archived_count = cur.fetchone()[0]
        assert archived_count == 1

        cur_j = repo._conn.execute(
            "SELECT reset_by_principal_id, event_count FROM evaluation_reset_journal WHERE tenant_id = ? AND case_id = ?",
            (t1, c1),
        )
        j_row = cur_j.fetchone()
        assert j_row is not None
        assert j_row[0] == "ADMIN-01"
        assert j_row[1] == 1
