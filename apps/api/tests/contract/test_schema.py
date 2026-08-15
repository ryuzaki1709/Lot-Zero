import json
from pathlib import Path

import jsonschema
import pytest


SCHEMA_PATH = Path(__file__).resolve().parents[4] / "contracts" / "incident-api.schema.json"


@pytest.fixture
def schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def minimal_projection() -> dict:
    return {
        "header": {
            "case_id": "CASE-001",
            "phase": "SCOPE_REVIEW",
            "environment_notice": "Evaluation tenant · synthetic records · no real outreach",
            "record_ids": ["CASE-001"],
        }
    }


def test_projection_requires_backing_record_ids(schema):
    projection = minimal_projection()
    projection["header"]["record_ids"] = []
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(projection, schema)


def test_projection_rejects_decorative_runtime_facts(schema):
    projection = minimal_projection()
    projection["runtime"] = {"model": "decorative fact"}

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(projection, schema)
