"""Unit tests for reducer authenticity: quantity threading, release unmaterialized action rejection, and dynamic DAG projections."""

from datetime import UTC, datetime
from decimal import Decimal
import pytest

from lot_zero.domain.errors import InvariantViolation
from lot_zero.domain.events import ContainmentReleasedEvent, ContainmentRequestedEvent
from lot_zero.domain.models import ContainmentAction, IncidentState, RecallCase
from lot_zero.domain.reducer import apply_event
from lot_zero.domain.selectors import build_incident_projection
from lot_zero.fixtures.loader import load_fixture, EvaluationFixture, Signal

TENANT_ID = "EVAL-TENANT-01"
CASE_ID = "EVAL-CASE-01"
NOW = datetime(2026, 8, 14, 12, 0, 0, tzinfo=UTC)


def make_test_state() -> IncidentState:
    case = RecallCase(
        case_id=CASE_ID,
        tenant_id=TENANT_ID,
        case_version=0,
        phase="signal_received",
        source_record_ids=("SRC-01",),
        created_at=NOW,
        updated_at=NOW,
    )
    return IncidentState(case=case, updated_at=NOW)


def test_containment_requested_event_threads_quantity_honestly():
    """Verify that ContainmentRequestedEvent folds its exact quantity without inventing 200."""
    initial_state = make_test_state()
    custom_qty = Decimal("137")

    event = ContainmentRequestedEvent(
        event_id="EVT-REQ-HOLD-137",
        tenant_id=TENANT_ID,
        case_id=CASE_ID,
        actor_id="RECALL-COORD-01",
        case_version=0,
        scope_id="SCOPE-01",
        scope_version=1,
        action_id="ACT-HOLD-137",
        policy_version="POL-01",
        target_record_ids=("LOT-CUSTOM-01", "LOT-CUSTOM-02"),
        quantity=custom_qty,
        occurred_at=NOW,
    )

    state_after = apply_event(initial_state, event)

    assert len(state_after.containment_actions) == 1
    action = state_after.containment_actions[0]
    assert action.action_id == "ACT-HOLD-137"
    assert action.quantity == custom_qty
    assert action.quantity != Decimal("200")
    assert action.target_record_ids == ("LOT-CUSTOM-01", "LOT-CUSTOM-02")


def test_containment_released_event_rejects_unmaterialized_action():
    """Verify that attempting to release a non-existent action raises InvariantViolation instead of falling back to demo constants."""
    state = make_test_state()

    event = ContainmentReleasedEvent(
        event_id="EVT-REL-01",
        tenant_id=TENANT_ID,
        case_id=CASE_ID,
        actor_id="RECALL-COORD-01",
        case_version=0,
        scope_id="SCOPE-01",
        action_id="NON-EXISTENT-ACTION-ID",
        retest_doc_id="LAB-RETEST-01",
        retest_doc_hash="a" * 64,
        occurred_at=NOW,
    )

    with pytest.raises(InvariantViolation, match="Cannot release unmaterialized containment action"):
        apply_event(state, event)


def test_containment_released_event_copies_authentic_target_action_data():
    """Verify that a valid release copies exact quantity and target ids from the prior hold action."""
    initial_state = make_test_state()
    prior_action = ContainmentAction(
        action_id="ACT-PRIOR-01",
        tenant_id=TENANT_ID,
        case_id=CASE_ID,
        scope_id="SCOPE-01",
        scope_version=1,
        action_type="provisional_hold",
        status="planned",
        target_record_ids=("LOT-AUTH-A", "LOT-AUTH-B"),
        quantity=Decimal("456"),
        policy_version="EVAL-HOLD-01",
        requested_at=NOW,
    )
    state_with_hold = initial_state.model_copy(update={"containment_actions": (prior_action,)})

    release_event = ContainmentReleasedEvent(
        event_id="EVT-REL-01",
        tenant_id=TENANT_ID,
        case_id=CASE_ID,
        actor_id="RECALL-COORD-01",
        case_version=0,
        scope_id="SCOPE-01",
        action_id="ACT-PRIOR-01",
        retest_doc_id="LAB-RETEST-01",
        retest_doc_hash="a" * 64,
        occurred_at=NOW,
    )

    state_after = apply_event(state_with_hold, release_event)

    release_action = next(a for a in state_after.containment_actions if a.action_type == "release_hold")
    assert release_action.quantity == Decimal("456")
    assert release_action.target_record_ids == ("LOT-AUTH-A", "LOT-AUTH-B")


def test_containment_requested_event_omitted_quantity_raises_validation_error():
    """Verify that constructing ContainmentRequestedEvent without a quantity field raises a ValidationError."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ContainmentRequestedEvent(  # type: ignore[call-arg]
            event_id="EVT-REQ-NO-QTY",
            tenant_id=TENANT_ID,
            case_id=CASE_ID,
            actor_id="RECALL-COORD-01",
            case_version=0,
            scope_id="SCOPE-01",
            scope_version=1,
            action_id="ACT-HOLD-NO-QTY",
            policy_version="POL-01",
            target_record_ids=("LOT-CUSTOM-01",),
            occurred_at=NOW,
        )


def test_genealogy_graph_adapts_to_scoped_ingredient_lot():
    """Verify that scope-derived ingredient lot dynamically drives the genealogy graph projection."""
    from lot_zero.domain.models import AffectedScope

    initial_state = make_test_state()
    scoped_lot = "ING-DYNAMIC-SCOPED-88"
    scope = AffectedScope(
        scope_id="SCOPE-01",
        tenant_id=TENANT_ID,
        case_id=CASE_ID,
        case_version=1,
        scope_version=1,
        status="proposed",
        affected_record_ids=("FP-100-L240814-A",),
        evidence_record_ids=("LAB-01",),
        affected_quantity=Decimal("100"),
        created_at=NOW,
        ingredient_lot=scoped_lot,
    )
    state_with_scope = initial_state.model_copy(update={"scopes": (scope,)})

    proj = build_incident_projection(state_with_scope)

    nodes = proj["genealogy"]["nodes"]
    ingredient_nodes = [n for n in nodes if n["type"] == "ingredient"]
    assert len(ingredient_nodes) == 1
    assert ingredient_nodes[0]["id"] == scoped_lot
    assert ingredient_nodes[0]["label"] == f"Organic Wheat Flour Lot {scoped_lot}"

    edges = proj["genealogy"]["edges"]
    supplier_edges = [e for e in edges if e["from"] == "SUP-MILLER-2026-08"]
    assert len(supplier_edges) == 1
    assert supplier_edges[0]["to"] == scoped_lot


@pytest.mark.anyio
async def test_simulate_signal_extraction_drives_genealogy_and_impact():
    """Drive the actual simulate-signal path with an extraction returning a different lot, and assert both the ingredient node and affected set reflect that lot consistently."""
    from unittest.mock import patch
    import httpx
    from lot_zero.app import app
    from lot_zero.domain.gemini_agent import ExtractedSignal

    custom_extracted_lot = "ING-CUSTOM-DIFF-5555"
    custom_signal = ExtractedSignal(
        source_id="LAB-SIGNAL-20260814-001",
        ingredient_lot=custom_extracted_lot,
        pathogen="Salmonella enterica serovar Typhimurium",
        spans=(),
        recommended_scope_records=(),
        extracted_at=NOW,
        model_version="gemini-3.5-flash (Mocked Extraction)",
        doc_hash="a" * 64,
        raw_text="Document text for ING-CUSTOM-DIFF-5555",
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Reset incident first
        res_reset = await client.post(
            "/api/evaluation/reset",
            headers={"X-API-Key": "key-recall-coord-01"},
        )
        assert res_reset.status_code == 200

        # Simulate signal with mocked extraction returning custom_extracted_lot
        with patch("lot_zero.app.analyze_safety_signal", return_value=custom_signal):
            res_sim = await client.post(
                "/api/evaluation/simulate-signal",
                headers={"X-API-Key": "key-recall-coord-01"},
            )
            assert res_sim.status_code == 200
            data = res_sim.json()

            # 1. Extraction result
            assert data["signal"]["ingredient_lot"] == custom_extracted_lot

            # 2. Genealogy graph projection must show custom_extracted_lot
            nodes = data["projection"]["genealogy"]["nodes"]
            ingredient_nodes = [n for n in nodes if n["type"] == "ingredient"]
            assert len(ingredient_nodes) == 1
            assert ingredient_nodes[0]["id"] == custom_extracted_lot
            assert ingredient_nodes[0]["label"] == f"Organic Wheat Flour Lot {custom_extracted_lot}"

            supplier_edges = [
                e for e in data["projection"]["genealogy"]["edges"] if e["from"] == "SUP-MILLER-2026-08"
            ]
            assert len(supplier_edges) == 1
            assert supplier_edges[0]["to"] == custom_extracted_lot

            # 3. Affected set reflects impact for this lot (0 units affected in fixture because fixture batches use ING-4417)
            assert data["projection"]["metrics"]["affected_inventory_quantity"] == 0.0
            assert data["projection"]["metrics"]["provisional_hold_quantity"] == 0.0


@pytest.mark.anyio
async def test_simulate_signal_extraction_drives_pathogen_hazard():
    """Drive simulate-signal with an extraction returning a custom pathogen and assert the graph's hazard field follows it."""
    from unittest.mock import patch
    import httpx
    from lot_zero.app import app
    from lot_zero.domain.gemini_agent import ExtractedSignal

    custom_pathogen = "Listeria monocytogenes (Line 4 Swab)"
    custom_signal = ExtractedSignal(
        source_id="LAB-SIGNAL-20260814-001",
        ingredient_lot="ING-4417",
        pathogen=custom_pathogen,
        spans=(),
        recommended_scope_records=(),
        extracted_at=NOW,
        model_version="gemini-3.5-flash (Mocked Extraction)",
        doc_hash="a" * 64,
        raw_text="Document text for Listeria monocytogenes",
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Reset incident first
        res_reset = await client.post(
            "/api/evaluation/reset",
            headers={"X-API-Key": "key-recall-coord-01"},
        )
        assert res_reset.status_code == 200

        # Simulate signal with mocked extraction returning custom_pathogen
        with patch("lot_zero.app.analyze_safety_signal", return_value=custom_signal):
            res_sim = await client.post(
                "/api/evaluation/simulate-signal",
                headers={"X-API-Key": "key-recall-coord-01"},
            )
            assert res_sim.status_code == 200
            data = res_sim.json()

            # 1. Extraction result
            assert data["signal"]["pathogen"] == custom_pathogen

            # 2. Genealogy graph projection hazard must follow custom_pathogen
            nodes = data["projection"]["genealogy"]["nodes"]
            ingredient_nodes = [n for n in nodes if n["type"] == "ingredient"]
            assert len(ingredient_nodes) == 1
            assert ingredient_nodes[0]["hazard"] == custom_pathogen


def test_build_incident_projection_empty_state_renders_no_ingredient_node():
    """Verify that when no scope exists on state, no incident nodes are drawn."""
    initial_state = make_test_state()
    assert len(initial_state.scopes) == 0

    proj = build_incident_projection(initial_state)
    assert proj["genealogy"]["nodes"] == []
    assert proj["genealogy"]["edges"] == []
    assert proj["genealogy"]["unresolved_edges"] == []


def test_build_incident_projection_scope_missing_ingredient_lot_raises_invariant_violation():
    """Verify that if a scope exists on state but carries no ingredient_lot, projection raises an InvariantViolation."""
    from lot_zero.domain.models import AffectedScope

    initial_state = make_test_state()
    scope_without_lot = AffectedScope(
        scope_id="SCOPE-NO-LOT-01",
        tenant_id=TENANT_ID,
        case_id=CASE_ID,
        case_version=1,
        scope_version=1,
        status="proposed",
        affected_record_ids=("FP-100-L240814-A",),
        evidence_record_ids=("LAB-01",),
        affected_quantity=Decimal("100"),
        created_at=NOW,
        ingredient_lot=None,  # Missing ingredient lot on an existing scope
    )
    state_corrupted_scope = initial_state.model_copy(update={"scopes": (scope_without_lot,)})

    with pytest.raises(InvariantViolation, match="carries no ingredient_lot"):
        build_incident_projection(state_corrupted_scope)


def test_notification_requested_event_omitted_recipients_raises_validation_error():
    """Verify that constructing NotificationRequestedEvent without recipient_ids raises ValidationError."""
    from pydantic import ValidationError
    from lot_zero.domain.events import NotificationRequestedEvent

    with pytest.raises(ValidationError):
        NotificationRequestedEvent(  # type: ignore[call-arg]
            event_id="EVT-NOTIF-01",
            tenant_id=TENANT_ID,
            case_id=CASE_ID,
            actor_id="OPS-01",
            case_version=0,
            scope_id="SCOPE-01",
            scope_version=1,
            packet_id="PKT-001",
            payload_version="PL-01",
            payload_hash="payload-sha256-verified-digest",
            policy_version="POL-01",
            occurred_at=NOW,
        )


def test_notification_requested_event_omitted_payload_hash_raises_validation_error():
    """Verify that constructing NotificationRequestedEvent without payload_hash raises ValidationError."""
    from pydantic import ValidationError
    from lot_zero.domain.events import NotificationRequestedEvent

    with pytest.raises(ValidationError):
        NotificationRequestedEvent(  # type: ignore[call-arg]
            event_id="EVT-NOTIF-01",
            tenant_id=TENANT_ID,
            case_id=CASE_ID,
            actor_id="OPS-01",
            case_version=0,
            scope_id="SCOPE-01",
            scope_version=1,
            packet_id="PKT-001",
            payload_version="PL-01",
            policy_version="POL-01",
            recipient_ids=("REC-001",),
            occurred_at=NOW,
        )


def test_notification_requested_event_folds_exact_recipient_ids_and_payload_hash():
    """Verify that folding a NotificationRequestedEvent with 3 recipients creates a packet with exactly those 3."""
    from lot_zero.domain.events import NotificationRequestedEvent

    initial_state = make_test_state()
    recipients = ("REC-ALPHA", "REC-BETA", "REC-GAMMA")
    payload_hash = "f4c8996fb92427ae41e4649b934ca495991b7852b855e3b0c44298fc1c149afb"

    event = NotificationRequestedEvent(
        event_id="EVT-NOTIF-3REC",
        tenant_id=TENANT_ID,
        case_id=CASE_ID,
        actor_id="OPS-01",
        case_version=0,
        scope_id="SCOPE-01",
        scope_version=1,
        packet_id="PKT-999",
        payload_version="PL-999",
        payload_hash=payload_hash,
        policy_version="POL-999",
        recipient_ids=recipients,
        occurred_at=NOW,
    )

    state_after = apply_event(initial_state, event)

    assert len(state_after.notification_packets) == 1
    packet = state_after.notification_packets[0]
    assert packet.packet_id == "PKT-999"
    assert packet.recipient_ids == recipients
    assert packet.payload_hash == payload_hash
    assert packet.status == "planned"


@pytest.mark.anyio
async def test_full_lifecycle_route_1_dual_signature_release_replay_equality():
    """Proving test: drive the full dual-signature release lifecycle through the API to phase 'closed',

    construct fresh state by rehydrating the persisted event stream, and assert 100% field-for-field equality.
    """
    import httpx
    from lot_zero.app import app, repository, DEFAULT_CASE_ID

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # Reset
        res_reset = await client.post("/api/evaluation/reset", headers={"X-API-Key": "key-recall-coord-01"})
        assert res_reset.status_code == 200

        # 1. Simulate signal
        res_sig = await client.post("/api/evaluation/simulate-signal", headers={"X-API-Key": "key-recall-coord-01"})
        assert res_sig.status_code == 200

        # 2. QA Lead approves containment
        res_app = await client.post(
            "/api/evaluation/approve-containment",
            headers={"X-API-Key": "key-qa-lead-01"},
            json={"rationale": "QA Lead biological risk confirmation"},
        )
        assert res_app.status_code == 200

        # 3. Customer Operations dispatches outbox
        res_out = await client.post("/api/evaluation/dispatch-outbox", headers={"X-API-Key": "key-ops-01"})
        assert res_out.status_code == 200

        # 4. Resolve ACK-006 via phone attestation
        res_ack = await client.post(
            "/api/evaluation/resolve-ack",
            headers={"X-API-Key": "key-ops-01"},
            json={
                "caller_id": "OPS-01",
                "recipient_contact": "Distributor Manager",
                "recipient_phone": "+1-612-555-0199",
                "call_timestamp": "2026-08-14T13:00:00Z",
                "attestation_notes": "Distributor confirmed warehouse quarantine",
            },
        )
        assert res_ack.status_code == 200

        # 5. Step 1 Release: QA Lead biological clearance
        res_rel1 = await client.post(
            "/api/evaluation/release-hold/step",
            headers={"X-API-Key": "key-qa-lead-01"},
            json={
                "retest_doc_id": "LAB-RETEST-9921",
                "retest_doc_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                "rationale": "QA Lead verified negative re-test certificate",
            },
        )
        assert res_rel1.status_code == 200

        # 6. Step 2 Release: Closure Authority operational release
        res_rel2 = await client.post(
            "/api/evaluation/release-hold/step",
            headers={"X-API-Key": "key-closure-auth-01"},
            json={
                "retest_doc_id": "LAB-RETEST-9921",
                "retest_doc_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                "rationale": "Closure Authority authorizes release to inventory",
            },
        )
        assert res_rel2.status_code == 200

        # 7. Request closure -> closed
        res_close = await client.post("/api/evaluation/request-closure", headers={"X-API-Key": "key-recall-coord-01"})
        assert res_close.status_code == 200
        assert res_close.json()["status"] == "closed"

        # Obtain live state from memory and rehydrated state from persistent SQLite event store
        from lot_zero.app import current_state as live_state

        loaded_state = await repository.load(DEFAULT_CASE_ID, tenant_id=TENANT_ID)
        assert loaded_state is not None

        # Assert full equality
        assert live_state.case.phase == "closed"
        assert loaded_state.case.phase == "closed"
        assert live_state == loaded_state


@pytest.mark.anyio
async def test_full_lifecycle_route_2_non_response_closure_replay_equality():
    """Proving test: drive the § 7.49 non-response closure lifecycle through the API to phase 'closed',

    construct fresh state by rehydrating the persisted event stream, and assert 100% field-for-field equality.
    """
    import httpx
    from lot_zero.app import app, repository, DEFAULT_CASE_ID

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # Reset
        res_reset = await client.post("/api/evaluation/reset", headers={"X-API-Key": "key-recall-coord-01"})
        assert res_reset.status_code == 200

        # 1. Simulate signal
        res_sig = await client.post("/api/evaluation/simulate-signal", headers={"X-API-Key": "key-recall-coord-01"})
        assert res_sig.status_code == 200

        # 2. QA Lead approves containment
        res_app = await client.post(
            "/api/evaluation/approve-containment",
            headers={"X-API-Key": "key-qa-lead-01"},
            json={"rationale": "QA Lead biological risk confirmation"},
        )
        assert res_app.status_code == 200

        # 3. Customer Operations dispatches outbox
        res_out = await client.post("/api/evaluation/dispatch-outbox", headers={"X-API-Key": "key-ops-01"})
        assert res_out.status_code == 200

        # 4. Close under 21 CFR § 7.49 non-response
        res_close = await client.post(
            "/api/evaluation/close-with-non-response",
            headers={"X-API-Key": "key-closure-auth-01"},
            json={
                "attempt_count": 3,
                "regulatory_filing_id": "FDA-REF-2026-0814-001",
                "good_faith_notes": "Documented 3 certified contact attempts; referred to FDA District Office.",
            },
        )
        assert res_close.status_code == 200
        assert res_close.json()["status"] == "closed_documented_non_response"

        # Obtain live state from memory and rehydrated state from persistent SQLite event store
        from lot_zero.app import current_state as live_state

        loaded_state = await repository.load(DEFAULT_CASE_ID, tenant_id=TENANT_ID)
        assert loaded_state is not None

        # Assert full equality
        assert live_state.case.phase == "closed"
        assert loaded_state.case.phase == "closed"
        assert live_state == loaded_state



