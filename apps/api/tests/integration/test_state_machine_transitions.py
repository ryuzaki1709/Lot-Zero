"""Integration tests for state machine transitions, AdvancePhaseCommand authorization, and event store verification."""

import pytest
from httpx import ASGITransport, AsyncClient

from datetime import UTC, datetime
from lot_zero.app import app
from lot_zero.domain.authority import Principal
from lot_zero.domain.commands import AdvancePhaseCommand
from lot_zero.domain.events import TransitionEvent
from lot_zero.domain.kernel import execute_command
from lot_zero.domain.models import RecallCase, IncidentState

TENANT_ID = "EVAL-TENANT-01"
CASE_ID = "EVAL-CASE-01"


def test_advance_phase_command_authorization_and_legality():
    """Verify role checks and illegal transition rejections for AdvancePhaseCommand."""
    now = datetime.now(UTC)
    case = RecallCase(
        case_id=CASE_ID,
        tenant_id=TENANT_ID,
        case_version=0,
        phase="signal_received",
        source_record_ids=("SRC-01",),
        created_at=now,
        updated_at=now,
    )
    state = IncidentState(case=case, updated_at=now)

    # 1. Illegal transition attempt (skipping scope_review directly to ack_monitoring)
    illegal_cmd = AdvancePhaseCommand(
        command_id="CMD-ADV-ILLEGAL-01",
        tenant_id=TENANT_ID,
        case_id=CASE_ID,
        actor_id="RECALL-COORD-01",
        case_version=0,
        target_phase="ack_monitoring",
    )
    coord_principal = Principal(tenant_id=TENANT_ID, principal_id="RECALL-COORD-01", roles=("recall_coordinator",))
    res_illegal = execute_command(state, illegal_cmd, coord_principal)
    assert not res_illegal.decision.allowed
    assert res_illegal.decision.code in ("ILLEGAL_PHASE_TRANSITION", "ROLE_NOT_AUTHORIZED")

    # 2. Unauthorized role attempt (customer_operations trying to advance to scope_review)
    ops_principal = Principal(tenant_id=TENANT_ID, principal_id="OPS-001", roles=("customer_operations",))
    legal_cmd = AdvancePhaseCommand(
        command_id="CMD-ADV-LEGAL-01",
        tenant_id=TENANT_ID,
        case_id=CASE_ID,
        actor_id="OPS-001",
        case_version=0,
        target_phase="scope_review",
    )
    res_unauthorized = execute_command(state, legal_cmd, ops_principal)
    assert not res_unauthorized.decision.allowed
    assert res_unauthorized.decision.code == "ROLE_NOT_AUTHORIZED"

    # 3. Authorized transition: recall_coordinator advancing to scope_review
    res_authorized = execute_command(state, legal_cmd, coord_principal)
    assert res_authorized.decision.allowed
    assert res_authorized.state.case.phase == "scope_review"
    assert len(res_authorized.events) == 1
    assert isinstance(res_authorized.events[0], TransitionEvent)
    assert res_authorized.events[0].target_phase == "scope_review"


@pytest.mark.anyio
async def test_dispatch_outbox_advances_phase_and_records_transition_event():
    """Verify that dispatching outbox advances phase to ack_monitoring and produces a TransitionEvent."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Reset
        reset_res = await client.post("/api/evaluation/reset", headers={"X-API-Key": "key-recall-coord-01"})
        assert reset_res.status_code == 200

        # 2. Simulate signal
        sim_res = await client.post("/api/evaluation/simulate-signal", headers={"X-API-Key": "key-recall-coord-01"})
        assert sim_res.status_code == 200

        # 3. QA approve containment
        app_res = await client.post(
            "/api/evaluation/approve-containment",
            json={"rationale": "Verified pathogen contamination in Lot ING-4417. Approving strict quarantine."},
            headers={"X-API-Key": "key-qa-lead-01"},
        )
        assert app_res.status_code == 200

        # 4. Customer Ops dispatch outbox
        dispatch_res = await client.post(
            "/api/evaluation/dispatch-outbox",
            headers={"X-API-Key": "key-ops-01"},
        )
        assert dispatch_res.status_code == 200
        proj = dispatch_res.json()["projection"]
        assert proj["header"]["phase"] == "ack_monitoring"

        # 5. Export audit and verify TransitionEvent exists in the cryptographic bundle
        audit_res = await client.get("/api/cases/EVAL-CASE-01/audit-export", headers={"X-API-Key": "key-closure-auth-01"})
        assert audit_res.status_code == 200
        audit_data = audit_res.json()

        # Verify events list contains transition event (kind 'advance')
        event_types = [e["event_type"] for e in audit_data["events"]]
        assert "advance" in event_types
