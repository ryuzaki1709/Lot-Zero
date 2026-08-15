"""Examples for deterministic recall impact calculation."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from lot_zero.fixtures.loader import load_fixture

TENANT_ID = "EVAL-TENANT-01"
CASE_ID = "EVAL-CASE-01"


def evaluation_inputs():
    """Build explicit domain inputs only from the authored evaluation fixture."""
    from lot_zero.domain.genealogy import GenealogyEdge, InventoryRecord, ShipmentRecord
    from lot_zero.domain.recall import FinishedLot
    from lot_zero.domain.scope import RecallScope, ScopePredicate

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
    return scope, products, edges, inventory, shipments


def compute_evaluation_impact():
    from lot_zero.domain.recall import compute_impact

    return compute_impact(*evaluation_inputs())


def test_golden_fixture_produces_only_the_authored_affected_lots() -> None:
    impact = compute_evaluation_impact()

    assert impact.affected_finished_lot_ids == (
        "FP-100-L240814-A",
        "FP-100-L240814-B",
    )
    assert impact.affected_inventory_quantity == Decimal("200")
    assert impact.affected_shipped_quantity == Decimal("70")
    assert impact.unaffected_hold_quantity == Decimal("0")


def test_adjacent_batch_is_evaluated_but_not_affected() -> None:
    impact = compute_evaluation_impact()
    adjacent = next(
        result
        for result in impact.evaluations
        if result.record_id == "FP-100-ADJ" and result.record_type == "finished_lot"
    )

    assert adjacent.affected is False
    assert adjacent.quantity == Decimal("100")


def test_broken_edge_is_explicitly_unresolved_without_an_inferred_transform() -> None:
    impact = compute_evaluation_impact()

    assert [(item.edge_id, item.target_id, item.status) for item in impact.unresolved_edges] == [
        ("EDGE-BROKEN-01", "TRANSFORM-MISSING-01", "unresolved")
    ]


def test_every_affected_result_retains_path_predicate_and_evidence_provenance() -> None:
    impact = compute_evaluation_impact()

    for result in impact.evaluations:
        if result.affected:
            assert result.paths
            assert result.predicate_ids == (
                "PRED-DATE-01",
                "PRED-INGREDIENT-01",
                "PRED-PRODUCT-01",
            )
            assert result.evidence_ids == ("LAB-SIGNAL-20260814-001",)


def test_cycle_is_safe_and_does_not_duplicate_affected_records() -> None:
    from lot_zero.domain.genealogy import GenealogyEdge
    from lot_zero.domain.recall import compute_impact

    scope, products, edges, inventory, shipments = evaluation_inputs()
    cyclic_edges = edges + (
        GenealogyEdge(
            edge_id="EDGE-CYCLE-01",
            tenant_id=TENANT_ID,
            case_id=CASE_ID,
            source_id="FP-100-L240814-A",
            target_id="ING-4417",
        ),
    )

    impact = compute_impact(scope, products, cyclic_edges, inventory, shipments)

    assert impact.affected_finished_lot_ids == (
        "FP-100-L240814-A",
        "FP-100-L240814-B",
    )
    assert len({result.record_id for result in impact.evaluations}) == len(impact.evaluations)


def test_scope_delta_exposes_only_newly_affected_finished_lots_as_targets() -> None:
    from lot_zero.domain.recall import compute_impact
    from lot_zero.domain.scope import compute_scope_delta

    scope, products, edges, inventory, shipments = evaluation_inputs()
    previous = compute_impact(scope, products[:1], edges[:1], inventory[:1], shipments)
    current = compute_impact(scope, products, edges, inventory, shipments)

    delta = compute_scope_delta(previous, current)

    assert delta.newly_affected == ("FP-100-L240814-B",)
    assert delta.no_longer_affected == ()
    assert delta.newly_unresolved_edge_ids == ("EDGE-BROKEN-01",)


def test_cross_tenant_and_duplicate_records_are_rejected() -> None:
    from lot_zero.domain.genealogy import InventoryRecord
    from lot_zero.domain.recall import compute_impact

    scope, products, edges, inventory, shipments = evaluation_inputs()
    cross_tenant = InventoryRecord(
        record_id="INV-OTHER-TENANT",
        tenant_id="OTHER-TENANT",
        case_id=CASE_ID,
        lot_id="FP-100-L240814-A",
        quantity=Decimal("1"),
    )
    with pytest.raises(ValueError, match="tenant_id"):
        compute_impact(scope, products, edges, inventory + (cross_tenant,), shipments)

    conflicting_duplicate = InventoryRecord(
        record_id=inventory[0].record_id,
        tenant_id=TENANT_ID,
        case_id=CASE_ID,
        lot_id=inventory[0].lot_id,
        quantity=Decimal("999"),
    )
    with pytest.raises(ValueError, match="duplicate"):
        compute_impact(scope, products, edges, inventory + (conflicting_duplicate,), shipments)
