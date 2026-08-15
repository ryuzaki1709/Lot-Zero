"""Tests for append-only SQLite event repository, optimistic concurrency, and replay equivalence."""

import tempfile
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from lot_zero.adapters.sqlite_repository import SqliteIncidentRepository
from lot_zero.domain.events import ScopeProposedEvent, TransitionEvent
from lot_zero.domain.models import ApprovalDecision, IncidentState, RecallCase
from lot_zero.ports.repositories import ConcurrencyError

NOW = datetime(2026, 8, 14, 12, 0, 0, tzinfo=UTC)
TENANT = "EVAL-TENANT-01"
CASE = "EVAL-CASE-01"


def make_initial_state(tenant_id: str = TENANT, case_id: str = CASE) -> IncidentState:
    return IncidentState(
        case=RecallCase(
            case_id=case_id,
            tenant_id=tenant_id,
            phase="signal_received",
            case_version=0,
            source_record_ids=("LAB-SIGNAL-01",),
            created_at=NOW,
            updated_at=NOW,
        ),
        updated_at=NOW,
    )


@pytest.mark.anyio
async def test_sqlite_append_and_load_rehydration():
    repo = SqliteIncidentRepository(db_path=":memory:", initial_state_factory=make_initial_state)
    try:
        # Initial load returns factory state
        state = await repo.load(CASE, tenant_id=TENANT)
        assert state is not None
        assert state.case.case_version == 0
        assert len(state.scopes) == 0

        # Append ScopeProposedEvent
        scope_event = ScopeProposedEvent(
            event_id="EVT-SCOPE-01",
            tenant_id=TENANT,
            case_id=CASE,
            actor_id="RECALL-COORD-01",
            case_version=0,
            scope_id="SCOPE-001",
            scope_version=1,
            affected_record_ids=("FP-100-A", "FP-100-B"),
            affected_quantity=Decimal("200"),
            evidence_record_ids=("LAB-SIGNAL-01",),
            occurred_at=NOW,
        )

        new_state = await repo.append(CASE, expected_version=0, events=[scope_event], tenant_id=TENANT)
        assert new_state.case.case_version == 1
        assert len(new_state.scopes) == 1
        assert new_state.scopes[0].scope_id == "SCOPE-001"
        assert new_state.scopes[0].affected_quantity == Decimal("200")
        assert len(new_state.ledger) == 1
        assert new_state.ledger[0].entry_type == "SCOPE_PROPOSED"

        # Reload from fresh query
        reloaded = await repo.load(CASE, tenant_id=TENANT)
        assert reloaded is not None
        assert reloaded.case.case_version == 1
        assert reloaded.scopes[0].scope_id == "SCOPE-001"
        assert reloaded.ledger[0].entry_hash == new_state.ledger[0].entry_hash
    finally:
        repo.close()


@pytest.mark.anyio
async def test_sqlite_optimistic_concurrency_conflict():
    repo = SqliteIncidentRepository(db_path=":memory:", initial_state_factory=make_initial_state)
    try:
        scope_event_1 = ScopeProposedEvent(
            event_id="EVT-SCOPE-01",
            tenant_id=TENANT,
            case_id=CASE,
            actor_id="RECALL-COORD-01",
            case_version=0,
            scope_id="SCOPE-001",
            scope_version=1,
            affected_record_ids=("FP-100-A",),
            affected_quantity=Decimal("100"),
            evidence_record_ids=("LAB-SIGNAL-01",),
            occurred_at=NOW,
        )

        scope_event_2 = ScopeProposedEvent(
            event_id="EVT-SCOPE-02",
            tenant_id=TENANT,
            case_id=CASE,
            actor_id="RECALL-COORD-02",
            case_version=0,
            scope_id="SCOPE-002",
            scope_version=1,
            affected_record_ids=("FP-100-B",),
            affected_quantity=Decimal("100"),
            evidence_record_ids=("LAB-SIGNAL-01",),
            occurred_at=NOW,
        )

        # First writer succeeds
        await repo.append(CASE, expected_version=0, events=[scope_event_1], tenant_id=TENANT)

        # Second writer attempting write with stale expected_version=0 fails with ConcurrencyError
        with pytest.raises(ConcurrencyError) as exc_info:
            await repo.append(CASE, expected_version=0, events=[scope_event_2], tenant_id=TENANT)

        assert exc_info.value.expected_version == 0
        assert exc_info.value.actual_version == 1
    finally:
        repo.close()


@pytest.mark.anyio
async def test_sqlite_restart_replay_equivalence():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_file = str(Path(tmp_dir) / "persistent_incident.db")

        # Session 1: Write events to database file
        repo_1 = SqliteIncidentRepository(db_path=db_file, initial_state_factory=make_initial_state)

        ev1 = ScopeProposedEvent(
            event_id="EVT-SCOPE-01",
            tenant_id=TENANT,
            case_id=CASE,
            actor_id="RECALL-COORD-01",
            case_version=0,
            scope_id="SCOPE-001",
            scope_version=1,
            affected_record_ids=("FP-100-A", "FP-100-B"),
            affected_quantity=Decimal("200"),
            evidence_record_ids=("LAB-SIGNAL-01",),
            occurred_at=NOW,
        )

        ev2 = ApprovalDecision(
            approval_id="APP-SCOPE-01",
            tenant_id=TENANT,
            case_id=CASE,
            approval_type="scope",
            decision="approved",
            rationale="Verified laboratory hazard finding",
            requester_id="RECALL-COORD-01",
            approver_id="QA-LEAD-01",
            approver_role="qa",
            case_version=1,
            boundary_version="BOUND-01",
            scope_id="SCOPE-001",
            scope_version=1,
            policy_version="POLICY-01",
            decided_at=NOW,
        )

        ev3 = TransitionEvent(
            event_id="EVT-TRANS-01",
            tenant_id=TENANT,
            case_id=CASE,
            case_version=2,
            kind="advance",
            target_phase="scope_review",
            occurred_at=NOW,
        )

        state_1 = await repo_1.append(CASE, expected_version=0, events=[ev1], tenant_id=TENANT)
        state_2 = await repo_1.append(CASE, expected_version=1, events=[ev2], tenant_id=TENANT)
        state_3 = await repo_1.append(CASE, expected_version=2, events=[ev3], tenant_id=TENANT)
        repo_1.close()

        # Session 2: Fresh repository instance connecting to the same DB file (simulating server restart)
        repo_2 = SqliteIncidentRepository(db_path=db_file, initial_state_factory=make_initial_state)
        try:
            replayed_state = await repo_2.load(CASE, tenant_id=TENANT)
        finally:
            repo_2.close()

        assert replayed_state is not None
        assert replayed_state.case.case_version == state_3.case.case_version == 3
        assert replayed_state.case.phase == "scope_review"
        assert len(replayed_state.scopes) == 1
        assert len(replayed_state.approvals) == 1
        assert len(replayed_state.ledger) == 3

        # Cryptographic ledger hashes match exactly
        for entry_replay, entry_orig in zip(replayed_state.ledger, state_3.ledger):
            assert entry_replay.entry_hash == entry_orig.entry_hash
            assert entry_replay.prior_entry_hash == entry_orig.prior_entry_hash


@pytest.mark.anyio
async def test_tenant_scoping_isolation():
    repo = SqliteIncidentRepository(db_path=":memory:", initial_state_factory=make_initial_state)
    try:
        ev_tenant_a = ScopeProposedEvent(
            event_id="EVT-SCOPE-A",
            tenant_id="TENANT-ALPHA",
            case_id=CASE,
            actor_id="COORD-A",
            case_version=0,
            scope_id="SCOPE-A",
            scope_version=1,
            affected_record_ids=("BATCH-A",),
            affected_quantity=Decimal("50"),
            evidence_record_ids=("LAB-01",),
            occurred_at=NOW,
        )

        ev_tenant_b = ScopeProposedEvent(
            event_id="EVT-SCOPE-B",
            tenant_id="TENANT-BETA",
            case_id=CASE,
            actor_id="COORD-B",
            case_version=0,
            scope_id="SCOPE-B",
            scope_version=1,
            affected_record_ids=("BATCH-B",),
            affected_quantity=Decimal("75"),
            evidence_record_ids=("LAB-02",),
            occurred_at=NOW,
        )

        # Both append at stream_version=1 under their own tenant_id
        state_a = await repo.append(CASE, expected_version=0, events=[ev_tenant_a], tenant_id="TENANT-ALPHA")
        state_b = await repo.append(CASE, expected_version=0, events=[ev_tenant_b], tenant_id="TENANT-BETA")

        assert state_a.scopes[0].scope_id == "SCOPE-A"
        assert state_b.scopes[0].scope_id == "SCOPE-B"

        # Loading with tenant filter returns only that tenant's state
        loaded_a = await repo.load(CASE, tenant_id="TENANT-ALPHA")
        loaded_b = await repo.load(CASE, tenant_id="TENANT-BETA")

        assert len(loaded_a.scopes) == 1
        assert loaded_a.scopes[0].scope_id == "SCOPE-A"

        assert len(loaded_b.scopes) == 1
        assert loaded_b.scopes[0].scope_id == "SCOPE-B"
    finally:
        repo.close()
