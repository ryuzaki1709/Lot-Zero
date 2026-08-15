"""Standard-library loader for the versioned synthetic evaluation fixture."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
from typing import Literal, Mapping


FIXTURE_VERSION = "evaluation-tenant-v1"
FIXTURE_DIRECTORY = Path(__file__).resolve().parents[5] / "fixtures" / FIXTURE_VERSION
_INTEGRITY_FILES = ("signal.json", "operations.json", "golden.json")


@dataclass(frozen=True)
class Signal:
    source_id: str
    received_at: datetime
    source_label: str
    ingredient_lot: str


@dataclass(frozen=True)
class FinishedLot:
    lot_id: str
    product_id: str
    quantity: int
    ingredient_lot: str


@dataclass(frozen=True)
class AdjacentBatch:
    lot_id: str
    product_id: str
    quantity: int
    ingredient_lot: str


@dataclass(frozen=True)
class Recipient:
    recipient_id: str


@dataclass(frozen=True)
class Acknowledgement:
    acknowledgement_id: str
    recipient_id: str
    status: str


@dataclass(frozen=True)
class GenealogyEdge:
    edge_id: str
    source_id: str
    target_id: str


@dataclass(frozen=True)
class Operations:
    affected_finished_lots: tuple[FinishedLot, ...]
    adjacent_unaffected_batch: AdjacentBatch
    recipients: tuple[Recipient, ...]
    acknowledgements: tuple[Acknowledgement, ...]
    broken_genealogy_edges: tuple[GenealogyEdge, ...]
    provisional_hold_id: str
    closure_id: str
    shipped_quantity: int


@dataclass(frozen=True)
class GoldenOutcomes:
    affected_inventory_quantity: int
    affected_shipped_quantity: int
    provisional_hold_quantity: int
    unaffected_hold_quantity: int
    outstanding_acknowledgement_ids: tuple[str, ...]
    unresolved_genealogy_edge_ids: tuple[str, ...]
    affected_operational_record_ids: tuple[str, ...]


@dataclass(frozen=True)
class EvaluationFixture:
    version: str
    tenant_id: str
    clock_start: datetime
    signal: Signal
    operations: Operations
    golden: GoldenOutcomes
    manifest_hashes: Mapping[str, str]
    real_world_domains: tuple[str, ...]


def _read_canonical_bytes(path: Path) -> bytes:
    content = path.read_bytes()
    if not content.endswith(b"\n") or b"\r" in content:
        raise ValueError(f"Fixture file is not canonical UTF-8 LF text: {path.name}")
    try:
        content.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError(f"Fixture file is not UTF-8: {path.name}") from error
    return content


def _object(value: object, name: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"Expected an object for {name}")
    return value


def _items(value: object, name: str) -> list[dict[str, object]]:
    if not isinstance(value, list):
        raise ValueError(f"Expected a list for {name}")
    return [_object(item, name) for item in value]


def _string(data: Mapping[str, object], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str):
        raise ValueError(f"Expected a string for {key}")
    return value


def _integer(data: Mapping[str, object], key: str) -> int:
    value = data.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"Expected an integer for {key}")
    return value


def _string_tuple(data: Mapping[str, object], key: str) -> tuple[str, ...]:
    values = data.get(key)
    if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
        raise ValueError(f"Expected strings for {key}")
    return tuple(values)


def _load_verified_documents() -> tuple[dict[str, object], dict[str, object], dict[str, object], dict[str, str]]:
    manifest = _object(json.loads(_read_canonical_bytes(FIXTURE_DIRECTORY / "manifest.json")), "manifest")
    if _string(manifest, "fixture_version") != FIXTURE_VERSION:
        raise ValueError("Fixture manifest version does not match requested fixture")
    file_hashes = _object(manifest.get("files"), "manifest.files")
    hashes = {name: _string(file_hashes, name) for name in _INTEGRITY_FILES}
    documents: dict[str, bytes] = {}
    for name in _INTEGRITY_FILES:
        content = _read_canonical_bytes(FIXTURE_DIRECTORY / name)
        if sha256(content).hexdigest() != hashes[name]:
            raise ValueError(f"SHA-256 mismatch for {name}")
        documents[name] = content
    return (
        _object(json.loads(documents["signal.json"]), "signal"),
        _object(json.loads(documents["operations.json"]), "operations"),
        _object(json.loads(documents["golden.json"]), "golden"),
        hashes,
    )


def load_fixture(version: Literal["evaluation-tenant-v1"]) -> EvaluationFixture:
    """Load the one synthetic fixture after checking each documented SHA-256 hash."""
    if version != FIXTURE_VERSION:
        raise ValueError(f"Unsupported fixture version: {version}")
    signal_data, operations_data, golden_data, hashes = _load_verified_documents()

    clock_start = datetime.fromisoformat(_string(signal_data, "received_at").replace("Z", "+00:00"))
    signal = Signal(
        source_id=_string(signal_data, "source_id"),
        received_at=clock_start,
        source_label=_string(signal_data, "source_label"),
        ingredient_lot=_string(signal_data, "canonical_ingredient_lot"),
    )
    affected_lots = tuple(
        FinishedLot(
            lot_id=_string(item, "lot_id"),
            product_id=_string(item, "product_id"),
            quantity=_integer(item, "quantity"),
            ingredient_lot=_string(item, "source_ingredient_lot"),
        )
        for item in _items(operations_data.get("affected_finished_lots"), "affected_finished_lots")
    )
    adjacent_data = _object(operations_data.get("adjacent_unaffected_batch"), "adjacent_unaffected_batch")
    adjacent_batch = AdjacentBatch(
        lot_id=_string(adjacent_data, "lot_id"),
        product_id=_string(adjacent_data, "product_id"),
        quantity=_integer(adjacent_data, "quantity"),
        ingredient_lot=_string(adjacent_data, "ingredient_lot"),
    )
    recipients = tuple(
        Recipient(recipient_id=_string(item, "recipient_id"))
        for item in _items(operations_data.get("recipients"), "recipients")
    )
    acknowledgements = tuple(
        Acknowledgement(
            acknowledgement_id=_string(item, "acknowledgement_id"),
            recipient_id=_string(item, "recipient_id"),
            status=_string(item, "status"),
        )
        for item in _items(operations_data.get("acknowledgements"), "acknowledgements")
    )
    all_edges = tuple(
        GenealogyEdge(
            edge_id=_string(item, "edge_id"),
            source_id=_string(item, "source_id"),
            target_id=_string(item, "target_id"),
        )
        for item in _items(operations_data.get("genealogy_edges"), "genealogy_edges")
    )
    known_operational_ids = {lot.lot_id for lot in affected_lots}
    broken_edges = tuple(edge for edge in all_edges if edge.target_id not in known_operational_ids)
    control_data = _object(operations_data.get("operational_controls"), "operational_controls")
    operations = Operations(
        affected_finished_lots=affected_lots,
        adjacent_unaffected_batch=adjacent_batch,
        recipients=recipients,
        acknowledgements=acknowledgements,
        broken_genealogy_edges=broken_edges,
        provisional_hold_id=_string(control_data, "provisional_hold_id"),
        closure_id=_string(control_data, "closure_id"),
        shipped_quantity=_integer(operations_data, "shipped_quantity"),
    )
    golden = GoldenOutcomes(
        affected_inventory_quantity=_integer(golden_data, "affected_inventory_quantity"),
        affected_shipped_quantity=_integer(golden_data, "affected_shipped_quantity"),
        provisional_hold_quantity=_integer(golden_data, "provisional_hold_quantity"),
        unaffected_hold_quantity=_integer(golden_data, "unaffected_hold_quantity"),
        outstanding_acknowledgement_ids=_string_tuple(golden_data, "outstanding_acknowledgement_ids"),
        unresolved_genealogy_edge_ids=_string_tuple(golden_data, "unresolved_genealogy_edge_ids"),
        affected_operational_record_ids=_string_tuple(golden_data, "affected_operational_record_ids"),
    )
    return EvaluationFixture(
        version=FIXTURE_VERSION,
        tenant_id="EVAL-TENANT-01",
        clock_start=clock_start,
        signal=signal,
        operations=operations,
        golden=golden,
        manifest_hashes=hashes,
        real_world_domains=(),
    )
