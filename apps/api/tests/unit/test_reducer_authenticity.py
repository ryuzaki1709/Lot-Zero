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

