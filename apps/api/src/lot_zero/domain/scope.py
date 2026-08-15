"""Explicit predicates and deterministic deltas for recall scope analysis."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Annotated, Literal

from pydantic import Field, model_validator

from .models import DomainRecord, Identifier

if TYPE_CHECKING:
    from .recall import RecallImpact


class ScopePredicate(DomainRecord):
    """A single auditable inclusion condition, never an inferred heuristic."""

    predicate_id: Identifier
    kind: Literal["ingredient_lot", "product_id", "produced_on"]
    expected_value: Identifier | None = None
    start_date: date | None = None
    end_date: date | None = None

    @model_validator(mode="after")
    def validate_shape(self) -> ScopePredicate:
        if self.kind == "produced_on":
            if self.expected_value is not None or self.start_date is None or self.end_date is None:
                raise ValueError("produced_on predicates require only start_date and end_date")
            if self.start_date > self.end_date:
                raise ValueError("produced_on start_date must not be after end_date")
        elif (
            self.expected_value is None
            or self.start_date is not None
            or self.end_date is not None
        ):
            raise ValueError(f"{self.kind} predicates require only expected_value")
        return self


class RecallScope(DomainRecord):
    """The complete, case-bounded set of authored predicates and evidence IDs."""

    scope_id: Identifier
    tenant_id: Identifier
    case_id: Identifier
    evidence_ids: Annotated[tuple[Identifier, ...], Field(min_length=1)]
    predicates: Annotated[tuple[ScopePredicate, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def validate_predicates(self) -> RecallScope:
        counts = {kind: 0 for kind in ("ingredient_lot", "product_id", "produced_on")}
        predicate_ids = set()
        for predicate in self.predicates:
            if predicate.predicate_id in predicate_ids:
                raise ValueError("scope predicate IDs must be unique")
            predicate_ids.add(predicate.predicate_id)
            counts[predicate.kind] += 1
        if counts["ingredient_lot"] != 1:
            raise ValueError("a recall scope requires exactly one ingredient_lot predicate")
        if counts["product_id"] > 1 or counts["produced_on"] > 1:
            raise ValueError("a recall scope supports at most one product and one date predicate")
        if len(set(self.evidence_ids)) != len(self.evidence_ids):
            raise ValueError("scope evidence IDs must be unique")
        return self

    @property
    def sorted_predicate_ids(self) -> tuple[str, ...]:
        return tuple(sorted(predicate.predicate_id for predicate in self.predicates))

    @property
    def sorted_evidence_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self.evidence_ids))


class ScopeDelta(DomainRecord):
    """The deterministic difference between two computed scopes, not an action plan."""

    tenant_id: Identifier
    case_id: Identifier
    previous_scope_id: Identifier
    current_scope_id: Identifier
    newly_affected: tuple[Identifier, ...] = ()
    no_longer_affected: tuple[Identifier, ...] = ()
    newly_unresolved_edge_ids: tuple[Identifier, ...] = ()
    resolved_edge_ids: tuple[Identifier, ...] = ()


def compute_scope_delta(previous: RecallImpact, current: RecallImpact) -> ScopeDelta:
    """Return stable finished-lot targets and genealogy changes between two impacts."""
    if previous.tenant_id != current.tenant_id:
        raise ValueError("scope impacts must share tenant_id")
    if previous.case_id != current.case_id:
        raise ValueError("scope impacts must share case_id")
    previous_lots = set(previous.affected_finished_lot_ids)
    current_lots = set(current.affected_finished_lot_ids)
    previous_unresolved = {edge.edge_id for edge in previous.unresolved_edges}
    current_unresolved = {edge.edge_id for edge in current.unresolved_edges}
    return ScopeDelta(
        tenant_id=current.tenant_id,
        case_id=current.case_id,
        previous_scope_id=previous.scope_id,
        current_scope_id=current.scope_id,
        newly_affected=tuple(sorted(current_lots - previous_lots)),
        no_longer_affected=tuple(sorted(previous_lots - current_lots)),
        newly_unresolved_edge_ids=tuple(sorted(current_unresolved - previous_unresolved)),
        resolved_edge_ids=tuple(sorted(previous_unresolved - current_unresolved)),
    )
