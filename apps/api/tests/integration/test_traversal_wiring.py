"""Integration tests for graph traversal engine wiring, golden oracle matching, and negative control verification."""

from datetime import date
from decimal import Decimal
import pytest
from httpx import ASGITransport, AsyncClient

from lot_zero.app import app
from lot_zero.domain.genealogy import GenealogyEdge, InventoryRecord, ShipmentRecord
from lot_zero.domain.recall import FinishedLot, compute_impact
from lot_zero.domain.scope import RecallScope, ScopePredicate
from lot_zero.domain.selectors import build_incident_projection
from lot_zero.fixtures.loader import load_fixture

TENANT_ID = "EVAL-TENANT-01"
CASE_ID = "EVAL-CASE-01"


def test_graph_traversal_matches_golden_oracle():
    """Verify that compute_impact matches every single field of golden.json strictly without hardcoding."""
    fixture = load_fixture("evaluation-tenant-v1")

    products = tuple(
        FinishedLot(
            record_id=lot.lot_id,
            tenant_id=TENANT_ID,
            case_id=CASE_ID,
            product_id=lot.product_id,
            lot_id=lot.lot_id,
            quantity=Decimal(str(lot.quantity)),
            produced_on=date(2026, 8, 14),
        )
        for lot in fixture.operations.affected_finished_lots
    ) + (
        FinishedLot(
            record_id=fixture.operations.adjacent_unaffected_batch.lot_id,
            tenant_id=TENANT_ID,
            case_id=CASE_ID,
            product_id=fixture.operations.adjacent_unaffected_batch.product_id,
            lot_id=fixture.operations.adjacent_unaffected_batch.lot_id,
            quantity=Decimal(str(fixture.operations.adjacent_unaffected_batch.quantity)),
            produced_on=date(2026, 8, 14),
        ),
    )
    edges = tuple(
        GenealogyEdge(
            edge_id=f"EDGE-{lot.lot_id}",
            tenant_id=TENANT_ID,
            case_id=CASE_ID,
            source_id=lot.ingredient_lot,
            target_id=lot.lot_id,
        )
        for lot in fixture.operations.affected_finished_lots
    ) + tuple(
        GenealogyEdge(
            edge_id=edge.edge_id,
            tenant_id=TENANT_ID,
            case_id=CASE_ID,
            source_id=edge.source_id,
            target_id=edge.target_id,
        )
        for edge in fixture.operations.broken_genealogy_edges
    )
    inventory = tuple(
        InventoryRecord(
            record_id=f"INV-{lot.lot_id}",
            tenant_id=TENANT_ID,
            case_id=CASE_ID,
            lot_id=lot.lot_id,
            quantity=Decimal(str(lot.quantity)),
        )
        for lot in fixture.operations.affected_finished_lots
    ) + (
        InventoryRecord(
            record_id="INV-FP-100-ADJ",
            tenant_id=TENANT_ID,
            case_id=CASE_ID,
            lot_id="FP-100-ADJ",
            quantity=Decimal(str(fixture.operations.adjacent_unaffected_batch.quantity)),
        ),
    )
    shipments = (
        ShipmentRecord(
            record_id="SHIP-FP-100-L240814-A",
            tenant_id=TENANT_ID,
            case_id=CASE_ID,
            lot_id="FP-100-L240814-A",
            quantity=Decimal(str(fixture.operations.shipped_quantity)),
        ),
    )
    scope = RecallScope(
        scope_id="SCOPE-EVAL-01",
        tenant_id=TENANT_ID,
        case_id=CASE_ID,
        evidence_ids=(fixture.signal.source_id,),
        predicates=(
            ScopePredicate(
                predicate_id="PRED-INGREDIENT-01",
                kind="ingredient_lot",
                expected_value=fixture.signal.source_label,
            ),
            ScopePredicate(
                predicate_id="PRED-PRODUCT-01",
                kind="product_id",
                expected_value="FP-100",
            ),
            ScopePredicate(
                predicate_id="PRED-DATE-01",
                kind="produced_on",
                start_date=date(2026, 8, 14),
                end_date=date(2026, 8, 14),
            ),
        ),
    )

    impact = compute_impact(scope, products, edges, inventory, shipments)

    # Assert exact match against fixture golden oracle
    assert impact.affected_finished_lot_ids == fixture.golden.affected_operational_record_ids
    assert int(impact.affected_inventory_quantity) == fixture.golden.affected_inventory_quantity
    assert int(impact.affected_shipped_quantity) == fixture.golden.affected_shipped_quantity
    assert int(impact.unaffected_hold_quantity) == fixture.golden.unaffected_hold_quantity
    assert tuple(e.edge_id for e in impact.unresolved_edges) == fixture.golden.unresolved_genealogy_edge_ids

    # Real negative control assertion (Zero false holds)
    assert "FP-100-ADJ" not in impact.affected_finished_lot_ids
    assert impact.unaffected_hold_quantity == 0


@pytest.mark.anyio
async def test_simulate_signal_endpoint_wires_traversal_and_surfaces_unresolved_edges():
    """Verify that POST /api/evaluation/simulate-signal uses graph traversal and returns unresolved boundaries."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Reset state first
        reset_res = await client.post("/api/evaluation/reset", headers={"X-API-Key": "key-recall-coord-01"})
        assert reset_res.status_code == 200

        # Simulate signal
        sim_res = await client.post("/api/evaluation/simulate-signal", headers={"X-API-Key": "key-recall-coord-01"})
        assert sim_res.status_code == 200
        data = sim_res.json()
        projection = data["projection"]

        # Assert traversal-derived metrics
        fixture = load_fixture("evaluation-tenant-v1")
        assert projection["metrics"]["affected_inventory_quantity"] == fixture.golden.affected_inventory_quantity
        assert projection["metrics"]["unaffected_hold_quantity"] == fixture.golden.unaffected_hold_quantity
        assert projection["metrics"]["unaffected_cleared_quantity"] == fixture.operations.adjacent_unaffected_batch.quantity

        # Assert unresolved edges are surfaced in genealogy projection
        unresolved = projection["genealogy"]["unresolved_edges"]
        assert len(unresolved) == len(fixture.golden.unresolved_genealogy_edge_ids)
        assert unresolved[0]["edge_id"] == "EDGE-BROKEN-01"
        assert unresolved[0]["target_id"] == "TRANSFORM-MISSING-01"
