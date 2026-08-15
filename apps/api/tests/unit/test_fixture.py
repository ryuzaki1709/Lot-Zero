import hashlib
from pathlib import Path

import pytest

from lot_zero.fixtures.loader import FIXTURE_DIRECTORY, load_fixture


INTEGRITY_FILE_NAMES = ("signal.json", "operations.json", "golden.json")


@pytest.fixture
def fixture():
    return load_fixture("evaluation-tenant-v1")


def test_fixture_is_fictional_deterministic_and_complete(fixture):
    assert fixture.tenant_id == "EVAL-TENANT-01"
    assert fixture.signal.ingredient_lot == "ING-4417"
    assert fixture.signal.source_id == "LAB-SIGNAL-20260814-001"
    assert fixture.signal.source_label == "ING 4417"
    assert fixture.clock_start.isoformat() == "2026-08-14T12:00:00+00:00"
    assert fixture.golden.outstanding_acknowledgement_ids == ("ACK-006",)
    assert not fixture.real_world_domains


def test_fixture_has_the_specified_operational_outcomes(fixture):
    assert tuple((lot.lot_id, lot.quantity) for lot in fixture.operations.affected_finished_lots) == (
        ("FP-100-L240814-A", 120),
        ("FP-100-L240814-B", 80),
    )
    assert tuple(lot.product_id for lot in fixture.operations.affected_finished_lots) == ("FP-100", "FP-100")
    assert fixture.operations.adjacent_unaffected_batch.lot_id == "FP-100-ADJ"
    assert fixture.operations.adjacent_unaffected_batch.ingredient_lot == "ING-4418"
    assert fixture.operations.adjacent_unaffected_batch.quantity == 100
    assert fixture.operations.shipped_quantity == 70
    assert fixture.operations.provisional_hold_id == "EVAL-HOLD-01"
    assert fixture.operations.closure_id == "EVAL-CLOSE-01"
    assert tuple(recipient.recipient_id for recipient in fixture.operations.recipients) == (
        "RECIPIENT-001",
        "RECIPIENT-002",
        "RECIPIENT-003",
        "RECIPIENT-004",
        "RECIPIENT-005",
        "RECIPIENT-006",
    )
    assert tuple(
        (acknowledgement.acknowledgement_id, acknowledgement.recipient_id, acknowledgement.status)
        for acknowledgement in fixture.operations.acknowledgements
    ) == (
        ("ACK-001", "RECIPIENT-001", "verified"),
        ("ACK-002", "RECIPIENT-002", "verified"),
        ("ACK-003", "RECIPIENT-003", "verified"),
        ("ACK-004", "RECIPIENT-004", "verified"),
        ("ACK-005", "RECIPIENT-005", "verified"),
        ("ACK-006", "RECIPIENT-006", "outstanding"),
    )
    assert fixture.golden.affected_inventory_quantity == 200
    assert fixture.golden.affected_shipped_quantity == 70
    assert fixture.golden.provisional_hold_quantity == 200
    assert fixture.golden.unaffected_hold_quantity == 0
    assert fixture.operations.broken_genealogy_edges[0].edge_id == "EDGE-BROKEN-01"
    assert fixture.operations.broken_genealogy_edges[0].target_id == "TRANSFORM-MISSING-01"
    assert fixture.golden.unresolved_genealogy_edge_ids == ("EDGE-BROKEN-01",)
    assert fixture.golden.affected_operational_record_ids == (
        "FP-100-L240814-A",
        "FP-100-L240814-B",
    )


def copied_fixture_directory(tmp_path: Path) -> Path:
    copied_fixture = tmp_path / "evaluation-tenant-v1"
    copied_fixture.mkdir()
    for source in FIXTURE_DIRECTORY.iterdir():
        destination = copied_fixture / source.name
        destination.write_bytes(source.read_bytes())
    return copied_fixture


@pytest.mark.parametrize("file_name", INTEGRITY_FILE_NAMES)
def test_loader_rejects_each_file_that_does_not_match_its_manifest_hash(
    tmp_path, monkeypatch, file_name
):
    copied_fixture = copied_fixture_directory(tmp_path)
    file_path = copied_fixture / file_name
    file_path.write_bytes(file_path.read_bytes().replace(b" ", b"  ", 1))
    monkeypatch.setattr("lot_zero.fixtures.loader.FIXTURE_DIRECTORY", copied_fixture)

    with pytest.raises(ValueError, match=rf"SHA-256 mismatch for {file_name}"):
        load_fixture("evaluation-tenant-v1")


@pytest.mark.parametrize("file_name", INTEGRITY_FILE_NAMES)
def test_manifest_hashes_match_all_canonical_fixture_bytes(file_name):
    fixture = load_fixture("evaluation-tenant-v1")
    assert fixture.manifest_hashes[file_name] == hashlib.sha256(
        (FIXTURE_DIRECTORY / file_name).read_bytes()
    ).hexdigest()


@pytest.mark.parametrize("file_name", INTEGRITY_FILE_NAMES)
@pytest.mark.parametrize(
    ("mutate", "expected_message"),
    (
        (lambda content: content.replace(b"\n", b"\r\n"), "not canonical UTF-8 LF text"),
        (lambda content: content.rstrip(b"\n"), "not canonical UTF-8 LF text"),
        (lambda content: b"\xff\n", "not UTF-8"),
    ),
)
def test_loader_rejects_noncanonical_fixture_bytes(
    tmp_path, monkeypatch, file_name, mutate, expected_message
):
    copied_fixture = copied_fixture_directory(tmp_path)
    file_path = copied_fixture / file_name
    file_path.write_bytes(mutate(file_path.read_bytes()))
    monkeypatch.setattr("lot_zero.fixtures.loader.FIXTURE_DIRECTORY", copied_fixture)

    with pytest.raises(ValueError, match=rf"{expected_message}: {file_name}"):
        load_fixture("evaluation-tenant-v1")
