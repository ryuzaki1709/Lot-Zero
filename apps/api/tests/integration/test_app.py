"""Integration test for FastAPI app endpoints, projections, SQLite persistence, and API-key security."""

import hashlib
import pytest
from fastapi.testclient import TestClient

from lot_zero.app import access_log, app, create_initial_state

KEY_QA = "key-qa-lead-01"
KEY_COORD = "key-recall-coord-01"
KEY_OPS = "key-ops-01"
KEY_CLOSURE = "key-closure-auth-01"
KEY_AGENT = "key-agent-svc-01"


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        # Guarantee clean baseline for every test
        test_client.post("/api/evaluation/reset", headers={"X-API-Key": KEY_COORD})
        access_log.clear()
        yield test_client


def test_health_check(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["tenant"] == "EVAL-TENANT-01"


def test_authentication_and_api_key_guards(client):
    # 1. Missing API key returns 401
    res_missing = client.get("/api/incidents/EVAL-CASE-01")
    assert res_missing.status_code == 401
    assert "Authentication required" in res_missing.json()["detail"]

    # 2. Invalid API key returns 401
    res_invalid = client.get("/api/incidents/EVAL-CASE-01", headers={"X-API-Key": "invalid-unknown-key"})
    assert res_invalid.status_code == 401
    assert "Invalid API key" in res_invalid.json()["detail"]

    # 3. Valid API key succeeds
    res_valid = client.get("/api/incidents/EVAL-CASE-01", headers={"X-API-Key": KEY_QA})
    assert res_valid.status_code == 200


def test_get_incident_projection_and_access_audit(client):
    res = client.get("/api/incidents/EVAL-CASE-01", headers={"X-API-Key": KEY_QA})
    assert res.status_code == 200
    data = res.json()
    assert data["header"]["case_id"] == "EVAL-CASE-01"
    assert data["header"]["environment_notice"] == "Evaluation tenant · synthetic records · no real outreach"
    assert "metrics" in data
    assert "genealogy" in data
    assert "signal" in data

    # Verify access log captured caller without fabrication
    assert len(access_log) >= 1
    assert access_log[-1].principal_id == "QA-LEAD-01"
    assert access_log[-1].action_type == "case_accessed"


def test_nonexistent_case_returns_404(client):
    res = client.get("/api/incidents/NON-EXISTENT-CASE", headers={"X-API-Key": KEY_COORD})
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


def test_hero_scenario_flow_state_assertions(client):
    """Verify that every step asserts on actual state properties rather than HTTP status echoes."""
    # 1. Simulate Signal -> Proposes Scope & Provisional Hold
    res_signal = client.post("/api/evaluation/simulate-signal", headers={"X-API-Key": KEY_COORD})
    assert res_signal.status_code == 200
    data_signal = res_signal.json()["projection"]
    assert len(data_signal["scopes"]) == 1
    assert data_signal["scopes"][0]["status"] == "proposed"
    assert data_signal["scopes"][0]["affected_quantity"] == 200.0
    assert len(data_signal["containment_actions"]) == 1
    assert data_signal["containment_actions"][0]["action_type"] == "provisional_hold"
    assert data_signal["metrics"]["provisional_hold_quantity"] == 200.0

    # 2. Approve Containment -> Converts to Firm Quarantine with QA Lead Signature
    res_app = client.post(
        "/api/evaluation/approve-containment",
        headers={"X-API-Key": KEY_QA},
        json={"role": "qa", "rationale": "Lab verified Salmonella enterica in Lot ING-4417"},
    )
    assert res_app.status_code == 200
    data_app = res_app.json()["projection"]
    qa_approvals = [a for a in data_app["approvals"] if a["approval_type"] == "containment"]
    assert len(qa_approvals) >= 1
    assert qa_approvals[0]["approver_id"] == "QA-LEAD-01"
    assert qa_approvals[0]["approver_name"] == "Dr. Elena Rostova (QA Lead)"

    # 3. Dispatch Outbox -> Dispatches 6 Notices with 5 Verified and 1 Outstanding (ACK-006)
    res_outbox = client.post("/api/evaluation/dispatch-outbox", headers={"X-API-Key": KEY_OPS})
    assert res_outbox.status_code == 200
    data_outbox = res_outbox.json()["projection"]
    
    assert len(data_outbox["acknowledgements"]) == 6
    verified_acks = [a for a in data_outbox["acknowledgements"] if a["status"] == "verified"]
    outstanding_acks = [a for a in data_outbox["acknowledgements"] if a["status"] == "outstanding"]
    assert len(verified_acks) == 5
    assert len(outstanding_acks) == 1
    assert outstanding_acks[0]["acknowledgement_id"] == "ACK-006"
    assert outstanding_acks[0]["recipient_id"] == "RECIPIENT-006"
    assert data_outbox["closure_gate"]["is_blocked"] is True
    assert data_outbox["metrics"]["outstanding_acknowledgements"] == 1

    # 4. Request Closure -> Honestly Blocked by Authority on ACK-006
    res_close = client.post("/api/evaluation/request-closure", headers={"X-API-Key": KEY_COORD})
    assert res_close.status_code == 200
    close_data = res_close.json()
    assert close_data["status"] == "closure_blocked"
    assert close_data["blocked"] is True
    assert "ACK-006" in close_data["outstanding_acknowledgements"]
    assert close_data["projection"]["header"]["phase"] != "closed"


def test_empty_and_blank_string_rejection_without_defaults(client):
    """Verify that posting empty or blank string JSON bodies is rejected with HTTP 422 and mutates nothing."""
    before = client.get("/api/incidents/EVAL-CASE-01", headers={"X-API-Key": KEY_COORD}).json()

    # 1. Release step empty body
    assert client.post("/api/evaluation/release-hold/step", headers={"X-API-Key": KEY_QA}).status_code == 422
    assert client.post("/api/evaluation/release-hold/step", headers={"X-API-Key": KEY_QA}, json={}).status_code == 422
    assert client.post("/api/evaluation/release-hold/step", headers={"X-API-Key": KEY_QA}, json={
        "retest_doc_id": " ", "retest_doc_hash": "", "role": "",
        "principal_id": " ", "rationale": "",
    }).status_code == 422

    # 2. Phone attestation empty and blank body
    assert client.post("/api/evaluation/resolve-ack", headers={"X-API-Key": KEY_OPS}).status_code == 422
    assert client.post("/api/evaluation/resolve-ack", headers={"X-API-Key": KEY_OPS}, json={}).status_code == 422
    assert client.post("/api/evaluation/resolve-ack", headers={"X-API-Key": KEY_OPS}, json={
        "caller_id": "", "recipient_contact": " ", "recipient_phone": "",
        "call_timestamp": "", "attestation_notes": "",
    }).status_code == 422

    # 3. Non-response closure empty and blank body
    assert client.post("/api/evaluation/close-with-non-response", headers={"X-API-Key": KEY_CLOSURE}).status_code == 422
    assert client.post("/api/evaluation/close-with-non-response", headers={"X-API-Key": KEY_CLOSURE}, json={}).status_code == 422
    assert client.post("/api/evaluation/close-with-non-response", headers={"X-API-Key": KEY_CLOSURE}, json={
        "principal_id": "", "attempt_count": 3, "regulatory_filing_id": "", "good_faith_notes": "",
    }).status_code == 422

    after = client.get("/api/incidents/EVAL-CASE-01", headers={"X-API-Key": KEY_COORD}).json()
    assert before["header"] == after["header"]
    assert len(before["approvals"]) == len(after["approvals"])


def test_sequential_dual_signature_release_authority(client):
    """Test authentic two-step sequential release authorization through domain authority kernel."""
    client.post("/api/evaluation/simulate-signal", headers={"X-API-Key": KEY_COORD})

    valid_hash = "e4b8c719a89d443210feeb89012356789abcdef0123456789abcdef012345678"
    invalid_hash = "not-a-valid-sha256"

    # Step 1 Negative: Invalid SHA-256 hash
    res_bad_hash = client.post(
        "/api/evaluation/release-hold/step",
        headers={"X-API-Key": KEY_QA},
        json={
            "retest_doc_id": "LAB-RETEST-SPL-99824-B",
            "retest_doc_hash": invalid_hash,
            "role": "qa",
            "principal_id": "QA-LEAD-01",
            "rationale": "Biological clearance recommended",
        },
    )
    assert res_bad_hash.status_code == 422

    # Step 2 Negative: Attempting closure authority release before QA signs
    res_early_close = client.post(
        "/api/evaluation/release-hold/step",
        headers={"X-API-Key": KEY_CLOSURE},
        json={
            "retest_doc_id": "LAB-RETEST-SPL-99824-B",
            "retest_doc_hash": valid_hash,
            "role": "closure_authority",
            "principal_id": "CLOSURE-AUTH-01",
            "rationale": "Attempting early release without QA",
        },
    )
    assert res_early_close.status_code == 400
    assert "operational inventory release requires prior biological clearance" in res_early_close.json()["detail"]

    # Step 1 Positive: QA Lead biological clearance signature
    res_qa = client.post(
        "/api/evaluation/release-hold/step",
        headers={"X-API-Key": KEY_QA},
        json={
            "retest_doc_id": "LAB-RETEST-SPL-99824-B",
            "retest_doc_hash": valid_hash,
            "role": "qa",
            "principal_id": "QA-LEAD-01",
            "rationale": "Lab re-test SPL-99824-B satisfies negative culture release criterion under FDA BAM Ch. 5.",
        },
    )
    assert res_qa.status_code == 200
    assert res_qa.json()["status"] == "release_step_approved"

    # Step 2 Positive: Closure Authority final operational un-hold signature (distinct principal)
    res_closure = client.post(
        "/api/evaluation/release-hold/step",
        headers={"X-API-Key": KEY_CLOSURE},
        json={
            "retest_doc_id": "LAB-RETEST-SPL-99824-B",
            "retest_doc_hash": valid_hash,
            "role": "closure_authority",
            "principal_id": "CLOSURE-AUTH-01",
            "rationale": "Operational release authorized following QA microbiology clearance SPL-99824-B.",
        },
    )
    assert res_closure.status_code == 200
    assert res_closure.json()["status"] == "release_step_approved"

    # Verify hold history was preserved alongside the release action
    data_final = res_closure.json()["projection"]
    actions = data_final["containment_actions"]
    action_types = [a["action_type"] for a in actions]
    assert "provisional_hold" in action_types
    assert "release_hold" in action_types


def test_section_749_non_response_closure_and_referral(client):
    """Test 21 CFR § 7.49 non-response closure pathway with certified FDA referral."""
    client.post("/api/evaluation/simulate-signal", headers={"X-API-Key": KEY_COORD})
    client.post(
        "/api/evaluation/approve-containment",
        headers={"X-API-Key": KEY_QA},
        json={"role": "qa", "rationale": "Hazard containment approved."},
    )
    client.post("/api/evaluation/dispatch-outbox", headers={"X-API-Key": KEY_OPS})

    # Close under documented non-response
    res_close = client.post(
        "/api/evaluation/close-with-non-response",
        headers={"X-API-Key": KEY_CLOSURE},
        json={
            "principal_id": "CLOSURE-AUTH-01",
            "attempt_count": 3,
            "regulatory_filing_id": "FDA-SAN-2026-NR-0091",
            "good_faith_notes": "Three certified delivery attempts completed without consignee response. Escalated to FDA District Office.",
        },
    )
    assert res_close.status_code == 200
    data = res_close.json()
    assert data["status"] == "closed_documented_non_response"
    assert data["regulatory_filing_id"] == "FDA-SAN-2026-NR-0091"
    assert data["projection"]["header"]["phase"] == "closed"


def test_phone_attestation_ack_resolution(client):
    """Test distributor phone attestation resolving ACK-006 with tamper-evident SHA-256 digest."""
    client.post("/api/evaluation/simulate-signal", headers={"X-API-Key": KEY_COORD})
    client.post(
        "/api/evaluation/approve-containment",
        headers={"X-API-Key": KEY_QA},
        json={"role": "qa", "rationale": "Hazard containment approved."},
    )
    client.post("/api/evaluation/dispatch-outbox", headers={"X-API-Key": KEY_OPS})

    # Resolve ACK-006 via signed phone attestation
    call_ts = "2026-08-14T15:30:00Z"
    notes = "Warehouse manager confirmed quarantine of 10 cases Lot FP-100-L240814-A in cold storage bay 3."
    caller = "Sarah Jenkins (Senior Recall Coordinator)"
    contact = "Marcus Vance (Logistics Director)"
    phone = "+1-555-019-2834"

    res_attest = client.post(
        "/api/evaluation/resolve-ack",
        headers={"X-API-Key": KEY_OPS},
        json={
            "caller_id": caller,
            "recipient_contact": contact,
            "recipient_phone": phone,
            "call_timestamp": call_ts,
            "attestation_notes": notes,
        },
    )
    assert res_attest.status_code == 200
    attest_data = res_attest.json()
    assert attest_data["status"] == "ack_resolved"
    assert len(attest_data["attestation_hash"]) == 64

    # Case should now close cleanly
    res_close = client.post("/api/evaluation/request-closure", headers={"X-API-Key": KEY_CLOSURE})
    assert res_close.status_code == 200
    assert res_close.json()["status"] == "closed"
    assert res_close.json()["blocked"] is False


def test_sse_ephemeral_token_authentication_and_forgery_protection(client):
    """Test HMAC-signed ephemeral SSE tokens: generation, expiry, and forgery protection."""
    # 1. Unauthenticated request to /api/sse-token returns 401
    res_unauth = client.post("/api/sse-token")
    assert res_unauth.status_code == 401

    # 2. Authenticated request issues valid token
    res_token = client.post("/api/sse-token", headers={"X-API-Key": KEY_QA})
    assert res_token.status_code == 200
    token_data = res_token.json()
    valid_token = token_data["token"]
    assert token_data["principal"] == "QA-LEAD-01"
    assert token_data["expires_in"] == 60

    # 3. Forged token with tampered payload returns 401
    parts = valid_token.split(".")
    forged_token = f"eyJwcmluY2lwYWxfaWQiOiJBVFRPUk5FWS0wMSJ9.{parts[1]}"
    res_forged = client.get(f"/api/incidents/EVAL-CASE-01/events?token={forged_token}")
    assert res_forged.status_code == 401
    assert "Invalid, forged, or expired token" in res_forged.json()["detail"]

    # 4. Expired token returns 401
    import base64
    import hashlib
    import hmac
    import json
    import time
    from lot_zero.auth import SSE_SECRET

    expired_payload = json.dumps({"principal_id": "QA-LEAD-01", "tenant_id": "EVAL-TENANT-01", "exp": int(time.time()) - 10}, separators=(",", ":"))
    b64_exp = base64.urlsafe_b64encode(expired_payload.encode()).decode().rstrip("=")
    exp_sig = hmac.new(SSE_SECRET.encode(), b64_exp.encode(), hashlib.sha256).hexdigest()
    expired_token = f"{b64_exp}.{exp_sig}"

    res_expired = client.get(f"/api/incidents/EVAL-CASE-01/events?token={expired_token}")
    assert res_expired.status_code == 401
    assert "Invalid, forged, or expired token" in res_expired.json()["detail"]
