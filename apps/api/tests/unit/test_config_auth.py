"""Unit tests for configuration loading, fail-fast validation, and auth resolution."""

import pytest

from lot_zero.auth import (
    create_sse_token,
    get_evaluation_personas,
    get_principal_for_key,
    verify_sse_token,
)
from lot_zero.config import load_config, validate_config_for_startup
from lot_zero.domain.authority import Principal


def test_production_fails_fast_on_missing_api_keys(monkeypatch):
    monkeypatch.setenv("LOT_ZERO_EVALUATION_MODE", "false")
    monkeypatch.delenv("LOT_ZERO_API_KEYS", raising=False)
    monkeypatch.setenv("LOT_ZERO_SSE_SECRET", "a" * 32)
    monkeypatch.setenv("LOT_ZERO_ALLOWED_ORIGINS", "http://localhost:8000")

    cfg = load_config()
    with pytest.raises(RuntimeError, match="LOT_ZERO_API_KEYS"):
        validate_config_for_startup(cfg)


def test_production_fails_fast_on_weak_sse_secret(monkeypatch):
    monkeypatch.setenv("LOT_ZERO_EVALUATION_MODE", "false")
    monkeypatch.setenv(
        "LOT_ZERO_API_KEYS", '{"k1": {"tenant_id": "T1", "principal_id": "P1", "roles": ["qa"]}}'
    )
    monkeypatch.setenv("LOT_ZERO_SSE_SECRET", "short_secret")
    monkeypatch.setenv("LOT_ZERO_ALLOWED_ORIGINS", "http://localhost:8000")

    cfg = load_config()
    with pytest.raises(RuntimeError, match="LOT_ZERO_SSE_SECRET"):
        validate_config_for_startup(cfg)


def test_production_fails_fast_on_missing_origins(monkeypatch):
    monkeypatch.setenv("LOT_ZERO_EVALUATION_MODE", "false")
    monkeypatch.setenv(
        "LOT_ZERO_API_KEYS", '{"k1": {"tenant_id": "T1", "principal_id": "P1", "roles": ["qa"]}}'
    )
    monkeypatch.setenv("LOT_ZERO_SSE_SECRET", "a" * 32)
    monkeypatch.delenv("LOT_ZERO_ALLOWED_ORIGINS", raising=False)

    cfg = load_config()
    with pytest.raises(RuntimeError, match="LOT_ZERO_ALLOWED_ORIGINS"):
        validate_config_for_startup(cfg)


def test_evaluation_mode_provides_exactly_five_human_personas(monkeypatch):
    """Evaluation mode must expose exactly five human personas and exclude agent-service."""
    monkeypatch.setenv("LOT_ZERO_EVALUATION_MODE", "true")
    personas = get_evaluation_personas()
    assert len(personas) == 5

    expected_principal_ids = {
        "RECALL-COORD-01",
        "QA-LEAD-01",
        "OPS-001",
        "CLOSURE-AUTH-01",
        "EVAL-ADMIN-01",
    }
    actual_principal_ids = {p["principal_id"] for p in personas}
    assert actual_principal_ids == expected_principal_ids

    # AGENT-SVC-01 and its key must NOT be in the browser persona list
    assert not any(p["principal_id"] == "AGENT-SVC-01" for p in personas)
    assert not any(p["key"] == "key-agent-svc-01" for p in personas)

    admin_persona = next((p for p in personas if p["key"] == "key-eval-admin-01"), None)
    assert admin_persona is not None
    assert admin_persona["can_reset"] is True

    admin_principal = get_principal_for_key("key-eval-admin-01")
    assert admin_principal is not None
    assert admin_principal.can_reset_evaluation is True

    coord_principal = get_principal_for_key("key-recall-coord-01")
    assert coord_principal is not None
    assert coord_principal.can_reset_evaluation is False


def test_agent_service_principal_internal_authentication_preserved(monkeypatch):
    """Internal AGENT-SVC-01 principal must still resolve for backend service authentication."""
    monkeypatch.setenv("LOT_ZERO_EVALUATION_MODE", "true")
    agent_principal = get_principal_for_key("key-agent-svc-01")
    assert agent_principal is not None
    assert agent_principal.principal_id == "AGENT-SVC-01"
    assert "agent_service" in agent_principal.roles
    assert agent_principal.tenant_id == "EVAL-TENANT-01"


def test_non_evaluation_mode_returns_no_synthetic_personas(monkeypatch):
    monkeypatch.setenv("LOT_ZERO_EVALUATION_MODE", "false")
    personas = get_evaluation_personas()
    assert personas == []


def test_hmac_sse_token_lifecycle_and_tamper_rejection(monkeypatch):
    monkeypatch.setenv("LOT_ZERO_SSE_SECRET", "test-secret-minimum-length-32-chars-long!")
    p = Principal(tenant_id="EVAL-TENANT-01", principal_id="USER-001", roles=("qa",))

    token = create_sse_token(p, ttl_seconds=60)
    assert isinstance(token, str) and "." in token

    verified = verify_sse_token(token)
    assert verified is not None
    assert verified.principal_id == "USER-001"
    assert verified.tenant_id == "EVAL-TENANT-01"

    # Tampered signature
    parts = token.split(".")
    tampered = f"{parts[0]}.bad_signature_hash_00000"
    assert verify_sse_token(tampered) is None
