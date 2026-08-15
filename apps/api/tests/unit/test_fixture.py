import hashlib
from pathlib import Path

import pytest

from lot_zero.fixtures.loader import FIXTURE_DIRECTORY, load_fixture


@pytest.fixture
def fixture():
    return load_fixture("evaluation-tenant-v1")


def test_fixture_is_fictional_deterministic_and_complete(fixture):
    assert fixture.tenant_id == "EVAL-TENANT-01"
    assert fixture.signal.ingredient_lot == "ING-4417"
    assert fixture.clock_start.isoformat() == "2026-08-14T12:00:00+00:00"
    assert fixture.golden.outstanding_acknowledgement_ids == ("ACK-006",)
    assert not fixture.real_world_domains


def test_fixture_has_the_specified_operational_outcomes(fixture):
    assert tuple((lot.lot_id, lot.quantity) for lot in fixture.operations.affected_finished_lots) == (
        ("FP-100-L240814-A", 120),
        ("FP-100-L240814-B", 80),
    )
    assert fixture.operations.adjacent_unaffected_batch.lot_id == "FP-100-ADJ"
    assert fixture.operations.adjacent_unaffected_batch.ingredient_lot == "ING-4418"
    assert fixture.golden.affected_inventory_quantity == 200
    assert fixture.golden.affected_shipped_quantity == 70
    assert fixture.golden.provisional_hold_quantity == 200
    assert fixture.golden.unaffected_hold_quantity == 0
    assert fixture.operations.broken_genealogy_edges[0].edge_id == "EDGE-BROKEN-01"
    assert fixture.operations.broken_genealogy_edges[0].target_id == "TRANSFORM-MISSING-01"
    assert fixture.golden.unresolved_genealogy_edge_ids == ("EDGE-BROKEN-01",)


def test_loader_rejects_a_file_that_does_not_match_its_manifest_hash(tmp_path, monkeypatch):
    copied_fixture = tmp_path / "evaluation-tenant-v1"
    copied_fixture.mkdir()
    for source in FIXTURE_DIRECTORY.iterdir():
        destination = copied_fixture / source.name
        destination.write_bytes(source.read_bytes())
    signal_path = copied_fixture / "signal.json"
    signal_path.write_bytes(signal_path.read_bytes().replace(b"ING-4417", b"ING-9999", 1))
    monkeypatch.setattr("lot_zero.fixtures.loader.FIXTURE_DIRECTORY", copied_fixture)

    with pytest.raises(ValueError, match="SHA-256 mismatch for signal.json"):
        load_fixture("evaluation-tenant-v1")


def test_manifest_hashes_match_canonical_fixture_bytes():
    fixture = load_fixture("evaluation-tenant-v1")
    assert fixture.manifest_hashes["signal.json"] == hashlib.sha256(
        (FIXTURE_DIRECTORY / "signal.json").read_bytes()
    ).hexdigest()
