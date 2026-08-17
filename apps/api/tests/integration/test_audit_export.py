"""Tests for tamper-evident audit export bundles, hash chaining, and tamper detection."""

import copy
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from lot_zero.adapters.sqlite_repository import SqliteIncidentRepository
from lot_zero.app import app
from lot_zero.domain.audit_export import (
    generate_audit_export,
    verify_audit_bundle,
)
from lot_zero.domain.events import (
    AcknowledgementRecordedEvent,
    ContainmentRequestedEvent,
    ScopeProposedEvent,
    TransitionEvent,
)
from lot_zero.domain.models import ApprovalDecision, IncidentState, RecallCase

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
async def test_audit_export_generation_and_verification():
    repo = SqliteIncidentRepository(db_path=":memory:", initial_state_factory=make_initial_state)
    try:
        tenant = "EVAL-TENANT-01"
        case_id = "CASE-AUDIT-TEST-01"

        ev1 = ScopeProposedEvent(
            event_id="EVT-01",
            tenant_id=tenant,
            case_id=case_id,
            actor_id="COORD-01",
            case_version=0,
            scope_id="SCOPE-01",
            scope_version=1,
            affected_record_ids=("FP-01",),
            affected_quantity=Decimal("150"),
            evidence_record_ids=("LAB-01",),
            occurred_at=NOW,
        )
        ev2 = ContainmentRequestedEvent(
            event_id="EVT-02",
            tenant_id=tenant,
            case_id=case_id,
            actor_id="COORD-01",
            case_version=1,
            scope_id="SCOPE-01",
            scope_version=1,
            action_id="ACT-01",
            policy_version="POL-01",
            target_record_ids=("FP-01",),
            quantity=Decimal("150"),
            occurred_at=NOW,
        )
        ev3 = ApprovalDecision(
            approval_id="APP-01",
            tenant_id=tenant,
            case_id=case_id,
            approval_type="containment",
            decision="approved",
            rationale="Quarantine approved by QA",
            requester_id="COORD-01",
            approver_id="QA-LEAD-01",
            approver_role="qa",
            case_version=2,
            boundary_version="BOUND-01",
            scope_id="SCOPE-01",
            scope_version=1,
            policy_version="POL-01",
            decided_at=NOW,
        )

        await repo.append(case_id, expected_version=0, events=[ev1, ev2, ev3], tenant_id=tenant)

        export = generate_audit_export(
            repo._conn,
            tenant_id=tenant,
            case_id=case_id,
            exported_by_principal_id="AUDITOR-001",
        )

        assert export is not None
        assert export.tenant_id == tenant
        assert export.case_id == case_id
        assert export.event_count == 3
        assert len(export.events) == 3
        assert export.exported_by_principal_id == "AUDITOR-001"

        # Verify unbroken hash chain
        assert export.events[0].prior_entry_hash is None
        assert export.events[1].prior_entry_hash == export.events[0].entry_hash
        assert export.events[2].prior_entry_hash == export.events[1].entry_hash

        # Complete cryptographic bundle verification
        is_valid, error = verify_audit_bundle(export)
        assert is_valid is True
        assert error is None
    finally:
        repo.close()


@pytest.mark.anyio
async def test_audit_export_tamper_detection():
    repo = SqliteIncidentRepository(db_path=":memory:", initial_state_factory=make_initial_state)
    try:
        tenant = "EVAL-TENANT-01"
        case_id = "CASE-AUDIT-TAMPER"

        ev1 = ScopeProposedEvent(
            event_id="EVT-01",
            tenant_id=tenant,
            case_id=case_id,
            actor_id="COORD-01",
            case_version=0,
            scope_id="SCOPE-01",
            scope_version=1,
            affected_record_ids=("FP-01",),
            affected_quantity=Decimal("100"),
            evidence_record_ids=("LAB-01",),
            occurred_at=NOW,
        )
        ev2 = ContainmentRequestedEvent(
            event_id="EVT-02",
            tenant_id=tenant,
            case_id=case_id,
            actor_id="COORD-01",
            case_version=1,
            scope_id="SCOPE-01",
            scope_version=1,
            action_id="ACT-01",
            policy_version="POL-01",
            target_record_ids=("FP-01",),
            quantity=Decimal("100"),
            occurred_at=NOW,
        )
        await repo.append(case_id, expected_version=0, events=[ev1, ev2], tenant_id=tenant)

        original_export = generate_audit_export(repo._conn, tenant, case_id, "AUDITOR-01")
        assert original_export is not None

        # 1. Tamper Scenario A: Altering event payload data
        tampered_payload = copy.deepcopy(original_export.model_dump())
        tampered_payload["events"][0]["payload"]["affected_quantity"] = "999.0"
        is_valid_a, error_a = verify_audit_bundle(tampered_payload)
        assert is_valid_a is False
        assert "Payload hash tampering detected" in error_a

        # 2. Tamper Scenario B: Altering entry_hash
        tampered_hash = copy.deepcopy(original_export.model_dump())
        tampered_hash["events"][0]["entry_hash"] = "0" * 64
        is_valid_b, error_b = verify_audit_bundle(tampered_hash)
        assert is_valid_b is False
        assert "Entry hash tampering detected" in error_b

        # 3. Tamper Scenario C: Breaking hash link
        tampered_link = copy.deepcopy(original_export.model_dump())
        tampered_link["events"][1]["prior_entry_hash"] = "f" * 64
        is_valid_c, error_c = verify_audit_bundle(tampered_link)
        assert is_valid_c is False
        assert "Broken hash chain link" in error_c

        # 4. Tamper Scenario D: Forging root digest
        tampered_root = copy.deepcopy(original_export.model_dump())
        tampered_root["top_level_digest"] = "e" * 64
        is_valid_d, error_d = verify_audit_bundle(tampered_root)
        assert is_valid_d is False
        assert "Top-level root digest mismatch" in error_d
    finally:
        repo.close()


def test_audit_export_endpoint_auth_and_tenant_scoping():
    with TestClient(app) as client:
        # 1. 401 without auth
        res_unauth = client.get("/api/cases/EVAL-CASE-01/audit-export")
        assert res_unauth.status_code == 401

        # 2. Simulate signal to generate events
        client.post("/api/evaluation/reset", headers={"X-API-Key": KEY_COORD})
        client.post("/api/evaluation/simulate-signal", headers={"X-API-Key": KEY_COORD})

        # 3. Successful audit export
        res_export = client.get("/api/cases/EVAL-CASE-01/audit-export", headers={"X-API-Key": KEY_COORD})
        assert res_export.status_code == 200
        bundle = res_export.json()

        assert bundle["case_id"] == "EVAL-CASE-01"
        assert bundle["tenant_id"] == "EVAL-TENANT-01"
        assert bundle["event_count"] >= 2
        assert len(bundle["top_level_digest"]) == 64

        # Verify exported bundle cryptographically
        is_valid, error = verify_audit_bundle(bundle)
        assert is_valid is True
        assert error is None

        # 4. Query non-existent case returns 404
        res_404 = client.get("/api/cases/NON-EXISTENT-CASE/audit-export", headers={"X-API-Key": KEY_COORD})
        assert res_404.status_code == 404
