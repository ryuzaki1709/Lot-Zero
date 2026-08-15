"""Tests for event-store read models, fast SQL projections, and strict tenant isolation."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from lot_zero.adapters.sqlite_repository import SqliteIncidentRepository
from lot_zero.app import app, repository
from lot_zero.domain.events import (
    AcknowledgementRecordedEvent,
    ContainmentReleasedEvent,
    ContainmentRequestedEvent,
    ScopeProposedEvent,
    TransitionEvent,
)
from lot_zero.domain.models import ApprovalDecision, IncidentState, RecallCase
from lot_zero.domain.projections import query_case_summaries

NOW = datetime(2026, 8, 14, 12, 0, 0, tzinfo=UTC)
KEY_QA = "key-qa-lead-01"
KEY_COORD = "key-recall-coord-01"
KEY_OPS = "key-ops-01"
KEY_CLOSURE = "key-closure-auth-01"


def make_initial_state(tenant_id: str, case_id: str) -> IncidentState:
    return IncidentState(
        case=RecallCase(
            case_id=case_id,
            tenant_id=tenant_id,
            phase="signal_received",
            case_version=0,
            source_record_ids=("LAB-01",),
            created_at=NOW,
            updated_at=NOW,
        ),
        updated_at=NOW,
    )


@pytest.mark.anyio
async def test_case_summary_projections_and_filters():
    repo = SqliteIncidentRepository(db_path=":memory:", initial_state_factory=make_initial_state)
    try:
        tenant = "EVAL-TENANT-01"

        # Case 1: Open Hold
        ev_c1 = ScopeProposedEvent(
            event_id="EVT-C1-01",
            tenant_id=tenant,
            case_id="CASE-OPEN-HOLD",
            actor_id="COORD-01",
            case_version=0,
            scope_id="SCOPE-01",
            scope_version=1,
            affected_record_ids=("FP-01",),
            affected_quantity=Decimal("150"),
            evidence_record_ids=("LAB-01",),
            occurred_at=NOW,
        )
        ev_c1_req = ContainmentRequestedEvent(
            event_id="EVT-C1-02",
            tenant_id=tenant,
            case_id="CASE-OPEN-HOLD",
            actor_id="COORD-01",
            case_version=1,
            scope_id="SCOPE-01",
            scope_version=1,
            action_id="ACT-01",
            policy_version="POL-01",
            target_record_ids=("FP-01",),
            occurred_at=NOW,
        )
        await repo.append("CASE-OPEN-HOLD", expected_version=0, events=[ev_c1, ev_c1_req], tenant_id=tenant)

        # Case 2: Pending QA Approval in scope review
        ev_c2_scope = ScopeProposedEvent(
            event_id="EVT-C2-01",
            tenant_id=tenant,
            case_id="CASE-PENDING-QA",
            actor_id="COORD-01",
            case_version=0,
            scope_id="SCOPE-02",
            scope_version=1,
            affected_record_ids=("FP-02",),
            affected_quantity=Decimal("75"),
            evidence_record_ids=("LAB-02",),
            occurred_at=NOW,
        )
        ev_c2_trans = TransitionEvent(
            event_id="EVT-C2-02",
            tenant_id=tenant,
            case_id="CASE-PENDING-QA",
            case_version=1,
            kind="advance",
            target_phase="scope_review",
            occurred_at=NOW,
        )
        await repo.append("CASE-PENDING-QA", expected_version=0, events=[ev_c2_scope, ev_c2_trans], tenant_id=tenant)

        # Case 3: Blocked by Refusal / Rejected Ack
        ev_c3_scope = ScopeProposedEvent(
            event_id="EVT-C3-01",
            tenant_id=tenant,
            case_id="CASE-REJECTED-ACK",
            actor_id="COORD-01",
            case_version=0,
            scope_id="SCOPE-03",
            scope_version=1,
            affected_record_ids=("FP-03",),
            affected_quantity=Decimal("50"),
            evidence_record_ids=("LAB-03",),
            occurred_at=NOW,
        )
        ev_c3_ack = AcknowledgementRecordedEvent(
            event_id="EVT-C3-02",
            tenant_id=tenant,
            case_id="CASE-REJECTED-ACK",
            actor_id="OPS-01",
            case_version=1,
            packet_id="PKT-03",
            acknowledgement_id="ACK-REFUSED-01",
            recipient_id="RECIP-03",
            acknowledgement_status="rejected",
            occurred_at=NOW,
        )
        await repo.append("CASE-REJECTED-ACK", expected_version=0, events=[ev_c3_scope, ev_c3_ack], tenant_id=tenant)

        # Case 4: Closed Case
        ev_c4_scope = ScopeProposedEvent(
            event_id="EVT-C4-01",
            tenant_id=tenant,
            case_id="CASE-CLOSED",
            actor_id="COORD-01",
            case_version=0,
            scope_id="SCOPE-04",
            scope_version=1,
            affected_record_ids=("FP-04",),
            affected_quantity=Decimal("30"),
            evidence_record_ids=("LAB-04",),
            occurred_at=NOW,
        )
        ev_c4_rel = ContainmentReleasedEvent(
            event_id="EVT-C4-02",
            tenant_id=tenant,
            case_id="CASE-CLOSED",
            actor_id="QA-01",
            case_version=1,
            action_id="ACT-04",
            scope_id="SCOPE-04",
            retest_doc_id="LAB-RETEST-04",
            retest_doc_hash="a" * 64,
            occurred_at=NOW,
        )
        ev_c4_close = TransitionEvent(
            event_id="EVT-C4-03",
            tenant_id=tenant,
            case_id="CASE-CLOSED",
            case_version=2,
            kind="advance",
            target_phase="scope_review",
            occurred_at=NOW,
        )
        await repo.append("CASE-CLOSED", expected_version=0, events=[ev_c4_scope, ev_c4_rel, ev_c4_close], tenant_id=tenant)

        # 1. Query all
        all_cases = query_case_summaries(repo._conn, tenant, filter_type="all")
        assert len(all_cases) == 4
        ids = {c.case_id for c in all_cases}
        assert ids == {"CASE-OPEN-HOLD", "CASE-PENDING-QA", "CASE-REJECTED-ACK", "CASE-CLOSED"}

        # 2. Query open holds
        open_hold_cases = query_case_summaries(repo._conn, tenant, filter_type="open_holds")
        open_ids = [c.case_id for c in open_hold_cases]
        assert "CASE-OPEN-HOLD" in open_ids
        assert "CASE-CLOSED" not in open_ids  # Closed & released case has no open holds

        # 3. Query pending QA
        pending_qa_cases = query_case_summaries(repo._conn, tenant, filter_type="pending_qa")
        pending_ids = [c.case_id for c in pending_qa_cases]
        assert "CASE-PENDING-QA" in pending_ids

        # 4. Query blocked by rejections
        rejection_cases = query_case_summaries(repo._conn, tenant, filter_type="blocked_by_rejections")
        rejection_ids = [c.case_id for c in rejection_cases]
        assert rejection_ids == ["CASE-REJECTED-ACK"]
        assert rejection_cases[0].rejected_ack_count == 1
    finally:
        repo.close()


@pytest.mark.anyio
async def test_projection_tenant_isolation():
    repo = SqliteIncidentRepository(db_path=":memory:", initial_state_factory=make_initial_state)
    try:
        # Case under Tenant Alpha
        ev_alpha = ScopeProposedEvent(
            event_id="EVT-ALPHA-01",
            tenant_id="TENANT-ALPHA",
            case_id="CASE-COMMON-NAME",
            actor_id="COORD-A",
            case_version=0,
            scope_id="SCOPE-A",
            scope_version=1,
            affected_record_ids=("FP-A",),
            affected_quantity=Decimal("100"),
            evidence_record_ids=("LAB-A",),
            occurred_at=NOW,
        )
        await repo.append("CASE-COMMON-NAME", expected_version=0, events=[ev_alpha], tenant_id="TENANT-ALPHA")

        # Case under Tenant Beta
        ev_beta = ScopeProposedEvent(
            event_id="EVT-BETA-01",
            tenant_id="TENANT-BETA",
            case_id="CASE-COMMON-NAME",
            actor_id="COORD-B",
            case_version=0,
            scope_id="SCOPE-B",
            scope_version=1,
            affected_record_ids=("FP-B",),
            affected_quantity=Decimal("200"),
            evidence_record_ids=("LAB-B",),
            occurred_at=NOW,
        )
        await repo.append("CASE-COMMON-NAME", expected_version=0, events=[ev_beta], tenant_id="TENANT-BETA")

        # Query Tenant Alpha
        alpha_cases = query_case_summaries(repo._conn, "TENANT-ALPHA", filter_type="all")
        assert len(alpha_cases) == 1
        assert alpha_cases[0].tenant_id == "TENANT-ALPHA"
        assert alpha_cases[0].open_hold_quantity == 100.0

        # Query Tenant Beta
        beta_cases = query_case_summaries(repo._conn, "TENANT-BETA", filter_type="all")
        assert len(beta_cases) == 1
        assert beta_cases[0].tenant_id == "TENANT-BETA"
        assert beta_cases[0].open_hold_quantity == 200.0

        # Query non-existent Tenant Gamma returns empty
        gamma_cases = query_case_summaries(repo._conn, "TENANT-GAMMA", filter_type="all")
        assert len(gamma_cases) == 0
    finally:
        repo.close()


def test_projection_http_endpoints():
    with TestClient(app) as client:
        # 1. Verify 401 without auth
        res_no_auth = client.get("/api/projections/cases")
        assert res_no_auth.status_code == 401

        # 2. Reset and simulate signal
        client.post("/api/evaluation/reset", headers={"X-API-Key": KEY_COORD})
        client.post("/api/evaluation/simulate-signal", headers={"X-API-Key": KEY_COORD})

        # 3. Query open holds
        res_open = client.get("/api/projections/cases/open-holds", headers={"X-API-Key": KEY_COORD})
        assert res_open.status_code == 200
        data = res_open.json()
        assert len(data) >= 1
        assert data[0]["case_id"] == "EVAL-CASE-01"
        assert data[0]["has_open_holds"] is True

        # 4. Query pending QA
        res_qa = client.get("/api/projections/cases/pending-qa", headers={"X-API-Key": KEY_QA})
        assert res_qa.status_code == 200

        # 5. Query blocked by rejections
        res_blocked = client.get("/api/projections/cases/blocked-by-rejections", headers={"X-API-Key": KEY_OPS})
        assert res_blocked.status_code == 200
        assert isinstance(res_blocked.json(), list)
