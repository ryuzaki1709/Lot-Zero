"""Pure, deterministic computation of recall impact from explicit operational records."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from typing import Literal

from .genealogy import (
    GenealogyEdge,
    GenealogyPath,
    InventoryRecord,
    ShipmentRecord,
    UnresolvedGenealogyEdge,
)
from .models import DomainRecord, Identifier, NonNegativeQuantity
from .scope import RecallScope, ScopePredicate


def _normalize_lot(value: str) -> str:
    """Normalize only leading/trailing space, case, and one ASCII separator alias."""
    trimmed = value.strip().upper()
    if not trimmed:
        return ""
    return trimmed.replace(" ", "-")


def exact_lot_match(expected: str, candidate: str) -> bool:
    """Match an authored lot exactly after the narrow ``ING 4417`` alias normalization."""
    expected_normalized = _normalize_lot(expected)
    candidate_normalized = _normalize_lot(candidate)
    return bool(
        expected_normalized
        and candidate_normalized
        and expected_normalized == candidate_normalized
    )


class FinishedLot(DomainRecord):
    """A manufactured lot that can be independently evaluated by a scope."""

    record_id: Identifier
    tenant_id: Identifier
    case_id: Identifier
    product_id: Identifier
    lot_id: Identifier
    quantity: NonNegativeQuantity
    produced_on: date


class ImpactEvaluation(DomainRecord):
    """One explicit result, including records considered and found unaffected."""

    record_id: Identifier
    tenant_id: Identifier
    case_id: Identifier
    record_type: Literal["finished_lot", "inventory", "shipment"]
    quantity: NonNegativeQuantity
    affected: bool
    paths: tuple[GenealogyPath, ...] = ()
    predicate_ids: tuple[Identifier, ...] = ()
    evidence_ids: tuple[Identifier, ...] = ()


class RecallImpact(DomainRecord):
    """A fully reproducible analysis result; it contains no containment decision."""

    impact_id: Identifier
    tenant_id: Identifier
    case_id: Identifier
    scope_id: Identifier
    evaluations: tuple[ImpactEvaluation, ...]
    affected_finished_lot_ids: tuple[Identifier, ...]
    affected_inventory_quantity: NonNegativeQuantity
    affected_shipped_quantity: NonNegativeQuantity
    unaffected_hold_quantity: NonNegativeQuantity
    unresolved_edges: tuple[UnresolvedGenealogyEdge, ...] = ()


def _require_single_boundary(
    scope: RecallScope, records: Iterable[DomainRecord], record_group: str
) -> None:
    for record in records:
        if getattr(record, "tenant_id") != scope.tenant_id:
            raise ValueError(f"{record_group} records must share scope tenant_id")
        if getattr(record, "case_id") != scope.case_id:
            raise ValueError(f"{record_group} records must share scope case_id")


def _unique_by_id[RecordT: DomainRecord](
    records: Iterable[RecordT], id_field: str, record_group: str
) -> dict[str, RecordT]:
    indexed: dict[str, RecordT] = {}
    for record in records:
        record_id = getattr(record, id_field)
        if record_id in indexed:
            raise ValueError(f"duplicate {record_group} {id_field}: {record_id}")
        indexed[record_id] = record
    return indexed


def _predicate(scope: RecallScope, kind: str) -> ScopePredicate | None:
    return next((predicate for predicate in scope.predicates if predicate.kind == kind), None)


def _product_matches_scope(product: FinishedLot, scope: RecallScope) -> bool:
    product_predicate = _predicate(scope, "product_id")
    if product_predicate is not None and product.product_id != product_predicate.expected_value:
        return False
    date_predicate = _predicate(scope, "produced_on")
    if date_predicate is not None:
        if date_predicate.start_date is None or date_predicate.end_date is None:
            raise ValueError("produced_on predicate is incomplete")
        if not date_predicate.start_date <= product.produced_on <= date_predicate.end_date:
            return False
    return True


def _reachable_paths(
    scope: RecallScope,
    products_by_lot: dict[str, FinishedLot],
    edges: tuple[GenealogyEdge, ...],
) -> tuple[dict[str, tuple[GenealogyPath, ...]], tuple[UnresolvedGenealogyEdge, ...]]:
    ingredient_predicate = _predicate(scope, "ingredient_lot")
    if ingredient_predicate is None or ingredient_predicate.expected_value is None:
        raise ValueError("scope ingredient_lot predicate is incomplete")
    adjacency: dict[str, list[GenealogyEdge]] = defaultdict(list)
    for edge in edges:
        adjacency[edge.source_id].append(edge)
    for outgoing in adjacency.values():
        outgoing.sort(key=lambda edge: edge.edge_id)

    paths_by_lot: dict[str, list[GenealogyPath]] = defaultdict(list)
    unresolved: dict[str, UnresolvedGenealogyEdge] = {}
    predicate_ids = scope.sorted_predicate_ids
    evidence_ids = scope.sorted_evidence_ids

    def walk(node_id: str, nodes: tuple[str, ...], edge_ids: tuple[str, ...]) -> None:
        for edge in adjacency.get(node_id, []):
            if edge.target_id in nodes:
                continue
            next_nodes = nodes + (edge.target_id,)
            next_edges = edge_ids + (edge.edge_id,)
            if edge.target_id in products_by_lot:
                paths_by_lot[edge.target_id].append(
                    GenealogyPath(
                        tenant_id=scope.tenant_id,
                        case_id=scope.case_id,
                        node_ids=next_nodes,
                        edge_ids=next_edges,
                        predicate_ids=predicate_ids,
                        evidence_ids=evidence_ids,
                    )
                )
            if edge.target_id not in products_by_lot and not adjacency.get(edge.target_id):
                unresolved[edge.edge_id] = UnresolvedGenealogyEdge(
                    edge_id=edge.edge_id,
                    tenant_id=scope.tenant_id,
                    case_id=scope.case_id,
                    source_id=edge.source_id,
                    target_id=edge.target_id,
                )
            walk(edge.target_id, next_nodes, next_edges)

    matching_sources = tuple(
        sorted(
            source_id
            for source_id in adjacency
            if exact_lot_match(ingredient_predicate.expected_value, source_id)
        )
    )
    for source_id in matching_sources:
        walk(source_id, (source_id,), ())
    sorted_paths = {
        lot_id: tuple(sorted(paths, key=lambda path: (path.edge_ids, path.node_ids)))
        for lot_id, paths in paths_by_lot.items()
    }
    return sorted_paths, tuple(unresolved[edge_id] for edge_id in sorted(unresolved))


def compute_impact(
    scope: RecallScope,
    product_master: tuple[FinishedLot, ...],
    genealogy: tuple[GenealogyEdge, ...],
    inventory: tuple[InventoryRecord, ...],
    shipments: tuple[ShipmentRecord, ...],
) -> RecallImpact:
    """Compute an immutable recall impact without approving or taking any external action."""
    _require_single_boundary(scope, product_master, "product")
    _require_single_boundary(scope, genealogy, "genealogy")
    _require_single_boundary(scope, inventory, "inventory")
    _require_single_boundary(scope, shipments, "shipment")
    product_records = _unique_by_id(product_master, "record_id", "product")
    products_by_lot = _unique_by_id(product_records.values(), "lot_id", "product lot")
    _unique_by_id(genealogy, "edge_id", "genealogy edge")
    _unique_by_id(inventory, "record_id", "inventory")
    _unique_by_id(shipments, "record_id", "shipment")

    paths_by_lot, unresolved_edges = _reachable_paths(scope, products_by_lot, tuple(genealogy))
    affected_lot_ids = tuple(
        product.lot_id
        for product in sorted(products_by_lot.values(), key=lambda product: product.lot_id)
        if product.lot_id in paths_by_lot and _product_matches_scope(product, scope)
    )
    affected_lot_id_set = set(affected_lot_ids)
    predicate_ids = scope.sorted_predicate_ids
    evidence_ids = scope.sorted_evidence_ids

    evaluations: list[ImpactEvaluation] = []
    for product in products_by_lot.values():
        affected = product.lot_id in affected_lot_id_set
        evaluations.append(
            ImpactEvaluation(
                record_id=product.record_id,
                tenant_id=scope.tenant_id,
                case_id=scope.case_id,
                record_type="finished_lot",
                quantity=product.quantity,
                affected=affected,
                paths=paths_by_lot.get(product.lot_id, ()) if affected else (),
                predicate_ids=predicate_ids if affected else (),
                evidence_ids=evidence_ids if affected else (),
            )
        )
    for record in inventory:
        affected = record.lot_id in affected_lot_id_set
        evaluations.append(
            ImpactEvaluation(
                record_id=record.record_id,
                tenant_id=scope.tenant_id,
                case_id=scope.case_id,
                record_type="inventory",
                quantity=record.quantity,
                affected=affected,
                paths=paths_by_lot.get(record.lot_id, ()) if affected else (),
                predicate_ids=predicate_ids if affected else (),
                evidence_ids=evidence_ids if affected else (),
            )
        )
    for record in shipments:
        affected = record.lot_id in affected_lot_id_set
        evaluations.append(
            ImpactEvaluation(
                record_id=record.record_id,
                tenant_id=scope.tenant_id,
                case_id=scope.case_id,
                record_type="shipment",
                quantity=record.quantity,
                affected=affected,
                paths=paths_by_lot.get(record.lot_id, ()) if affected else (),
                predicate_ids=predicate_ids if affected else (),
                evidence_ids=evidence_ids if affected else (),
            )
        )
    sorted_evaluations = tuple(
        sorted(evaluations, key=lambda result: (result.record_type, result.record_id))
    )
    affected_inventory = sum(
        (record.quantity for record in inventory if record.lot_id in affected_lot_id_set),
        Decimal("0"),
    )
    affected_shipped = sum(
        (record.quantity for record in shipments if record.lot_id in affected_lot_id_set),
        Decimal("0"),
    )
    return RecallImpact(
        impact_id=f"impact:{scope.scope_id}",
        tenant_id=scope.tenant_id,
        case_id=scope.case_id,
        scope_id=scope.scope_id,
        evaluations=sorted_evaluations,
        affected_finished_lot_ids=affected_lot_ids,
        affected_inventory_quantity=affected_inventory,
        affected_shipped_quantity=affected_shipped,
        unaffected_hold_quantity=Decimal("0"),
        unresolved_edges=unresolved_edges,
    )
