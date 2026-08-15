"""Strict input and provenance records for deterministic genealogy traversal."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from .models import DomainRecord, Identifier, NonNegativeQuantity


class GenealogyEdge(DomainRecord):
    """One authored source-to-target relationship inside a tenant and case."""

    edge_id: Identifier
    tenant_id: Identifier
    case_id: Identifier
    source_id: Identifier
    target_id: Identifier


class InventoryRecord(DomainRecord):
    """A current quantity tied explicitly to one finished lot."""

    record_id: Identifier
    tenant_id: Identifier
    case_id: Identifier
    lot_id: Identifier
    quantity: NonNegativeQuantity


class ShipmentRecord(DomainRecord):
    """A shipped quantity tied explicitly to one finished lot."""

    record_id: Identifier
    tenant_id: Identifier
    case_id: Identifier
    lot_id: Identifier
    quantity: NonNegativeQuantity


class GenealogyPath(DomainRecord):
    """One simple, authorable path that justifies a reached finished lot."""

    tenant_id: Identifier
    case_id: Identifier
    node_ids: Annotated[tuple[Identifier, ...], Field(min_length=2)]
    edge_ids: Annotated[tuple[Identifier, ...], Field(min_length=1)]
    predicate_ids: Annotated[tuple[Identifier, ...], Field(min_length=1)]
    evidence_ids: Annotated[tuple[Identifier, ...], Field(min_length=1)]


class UnresolvedGenealogyEdge(DomainRecord):
    """A reached edge whose target cannot be resolved from the supplied records."""

    edge_id: Identifier
    tenant_id: Identifier
    case_id: Identifier
    source_id: Identifier
    target_id: Identifier
    status: Literal["unresolved"] = "unresolved"
