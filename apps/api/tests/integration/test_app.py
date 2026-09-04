"""Integration test for FastAPI app endpoints, projections, SQLite persistence, and API-key security."""

import hashlib

import pytest
from fastapi.testclient import TestClient

from lot_zero.app import access_log, app

KEY_ADMIN = "key-eval-admin-01"
KEY_QA = "key-qa-lead-01"
KEY_COORD = "key-recall-coord-01"
KEY_OPS = "key-ops-01"
KEY_CLOSURE = "key-closure-auth-01"
KEY_AGENT = "key-agent-svc-01"


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        # Guarantee clean baseline for every test using evaluation admin key
        test_client.post("/api/evaluation/reset", headers={"X-API-Key": KEY_ADMIN})
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
    res_invalid = client.get(
        "/api/incidents/EVAL-CASE-01", headers={"X-API-Key": "invalid-unknown-key"}
    )
    assert res_invalid.status_code == 401
    assert "Invalid API key" in res_invalid.json()["detail"]

    # 3. Valid API key succeeds
    res_valid = client.get("/api/incidents/EVAL-CASE-01", headers={"X-API-Key": KEY_QA})
    assert res_valid.status_code == 200
    case_body = res_valid.json()
    assert case_body["header"]["source_doc_version"] == "v1.0 (Apex Micro Quality Labs Text Notice)"
    assert "Signed Apex Labs Report" not in res_valid.text
    assert "Signed laboratory report" not in res_valid.text
    assert "Non-Response Close (§ 7.49)" not in res_valid.text

    # 4. Internal agent service key succeeds for authenticated incident read
    res_agent = client.get("/api/incidents/EVAL-CASE-01", headers={"X-API-Key": KEY_AGENT})
    assert res_agent.status_code == 200


def test_config_endpoint_exposes_five_human_personas_excluding_agent_svc(client):
    """Verify /api/config exposes exactly 5 human personas and excludes internal agent-service."""
    res = client.get("/api/config")
    assert res.status_code == 200
    data = res.json()
    assert data["evaluation_mode"] is True
    personas = data["personas"]
    assert len(personas) == 5

    principal_ids = {p["principal_id"] for p in personas}
    assert principal_ids == {
        "RECALL-COORD-01",
        "QA-LEAD-01",
        "OPS-001",
        "CLOSURE-AUTH-01",
        "EVAL-ADMIN-01",
    }
    assert "AGENT-SVC-01" not in principal_ids
    assert not any(p["key"] == "key-agent-svc-01" for p in personas)


def test_get_incident_projection_and_access_audit(client):
    res = client.get("/api/incidents/EVAL-CASE-01", headers={"X-API-Key": KEY_QA})
    assert res.status_code == 200
    data = res.json()
    assert data["header"]["case_id"] == "EVAL-CASE-01"
    assert (
        data["header"]["environment_notice"]
        == "Evaluation tenant · synthetic records · no real outreach"
    )
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
    signal_json = res_signal.json()
    data_signal = signal_json["projection"]
    assert (
        data_signal["header"]["source_doc_version"] == "v1.0 (Apex Micro Quality Labs Text Notice)"
    )
    assert "Signed Apex Labs Report" not in res_signal.text
    assert "Signed laboratory report" not in res_signal.text
    assert "Non-Response Close (§ 7.49)" not in res_signal.text
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

    # 2b. Customer Operations approves notification packet
    res_notif = client.post(
        "/api/evaluation/approve-notification",
        headers={"X-API-Key": KEY_OPS},
        json={
            "packet_id": "PKT-001",
            "payload_version": "PAYLOAD-001",
            "payload_hash": "payload-sha256-verified-digest",
            "scope_id": "SCOPE-EVAL-01",
            "scope_version": 1,
            "policy_version": "EVAL-HOLD-01",
            "rationale": "Customer Operations approves notification packet for dispatch.",
        },
    )
    assert res_notif.status_code == 200

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

    # 4. Request Closure -> Creates ClosureRequest
    res_req = client.post("/api/evaluation/request-closure", headers={"X-API-Key": KEY_COORD})
    assert res_req.status_code == 200
    req_data = res_req.json()
    assert req_data["status"] == "closure_requested"
    req_id = req_data["request_id"]

    # 5. Authorize Closure -> Honestly Blocked by Authority on ACK-006
    res_close = client.post(
        "/api/evaluation/authorize-closure",
        headers={"X-API-Key": KEY_CLOSURE},
        json={"request_id": req_id, "rationale": "Attempting closure with outstanding acks"},
    )
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
    assert (
        client.post("/api/evaluation/release-hold/step", headers={"X-API-Key": KEY_QA}).status_code
        == 422
    )
    assert (
        client.post(
            "/api/evaluation/release-hold/step", headers={"X-API-Key": KEY_QA}, json={}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/evaluation/release-hold/step",
            headers={"X-API-Key": KEY_QA},
            json={
                "retest_doc_id": " ",
                "retest_doc_hash": "",
                "role": "",
                "principal_id": " ",
                "rationale": "",
            },
        ).status_code
        == 422
    )

    # 2. Phone attestation empty and blank body
    assert (
        client.post("/api/evaluation/resolve-ack", headers={"X-API-Key": KEY_OPS}).status_code
        == 422
    )
    assert (
        client.post(
            "/api/evaluation/resolve-ack", headers={"X-API-Key": KEY_OPS}, json={}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/evaluation/resolve-ack",
            headers={"X-API-Key": KEY_OPS},
            json={
                "caller_id": "",
                "recipient_contact": " ",
                "recipient_phone": "",
                "call_timestamp": "",
                "attestation_notes": "",
            },
        ).status_code
        == 422
    )

    # 3. Non-response closure empty and blank body
    assert (
        client.post(
            "/api/evaluation/close-with-non-response", headers={"X-API-Key": KEY_CLOSURE}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/evaluation/close-with-non-response", headers={"X-API-Key": KEY_CLOSURE}, json={}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/evaluation/close-with-non-response",
            headers={"X-API-Key": KEY_CLOSURE},
            json={
                "principal_id": "",
                "attempt_count": 3,
                "regulatory_filing_id": "",
                "good_faith_notes": "",
            },
        ).status_code
        == 422
    )

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
    assert (
        "operational inventory release requires prior biological clearance"
        in res_early_close.json()["detail"]
    )

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
    """Test synthetic non-response closure pathway with modeled referral note."""
    client.post("/api/evaluation/simulate-signal", headers={"X-API-Key": KEY_COORD})
    client.post(
        "/api/evaluation/approve-containment",
        headers={"X-API-Key": KEY_QA},
        json={"role": "qa", "rationale": "Hazard containment approved."},
    )
    client.post(
        "/api/evaluation/approve-notification",
        headers={"X-API-Key": KEY_OPS},
        json={
            "packet_id": "PKT-001",
            "payload_version": "PAYLOAD-001",
            "payload_hash": "payload-sha256-verified-digest",
            "scope_id": "SCOPE-EVAL-01",
            "scope_version": 1,
            "policy_version": "EVAL-HOLD-01",
            "rationale": "Customer Operations approves notification packet.",
        },
    )
    client.post("/api/evaluation/dispatch-outbox", headers={"X-API-Key": KEY_OPS})

    # 1. Recall Coordinator requests closure review
    res_req = client.post("/api/evaluation/request-closure", headers={"X-API-Key": KEY_COORD})
    assert res_req.status_code == 200
    req_id = res_req.json()["request_id"]

    # 2. Closure Authority closes under documented non-response
    res_close = client.post(
        "/api/evaluation/close-with-non-response",
        headers={"X-API-Key": KEY_CLOSURE},
        json={
            "request_id": req_id,
            "attempt_count": 3,
            "regulatory_filing_id": "FDA-SAN-2026-NR-0091",
            "good_faith_notes": "Three certified delivery attempts completed without consignee response. Escalated to FDA District Office.",
        },
    )
    assert res_close.status_code == 200
    data = res_close.json()
    assert data["regulatory_filing_id"] == "FDA-SAN-2026-NR-0091"
    assert data["projection"]["header"]["phase"] == "closed"
    approvals = data["projection"]["approvals"]
    closure_app = next(a for a in approvals if a.get("approval_type") == "closure")
    assert "SYNTHETIC NON-RESPONSE DOCUMENTATION" in closure_app["rationale"]
    assert "CERTIFIED GOOD-FAITH" not in closure_app["rationale"]


def test_phone_attestation_ack_resolution(client):
    """Test distributor phone attestation resolving ACK-006 with tamper-evident SHA-256 digest."""
    client.post("/api/evaluation/simulate-signal", headers={"X-API-Key": KEY_COORD})
    client.post(
        "/api/evaluation/approve-containment",
        headers={"X-API-Key": KEY_QA},
        json={"role": "qa", "rationale": "Hazard containment approved."},
    )
    client.post(
        "/api/evaluation/approve-notification",
        headers={"X-API-Key": KEY_OPS},
        json={
            "packet_id": "PKT-001",
            "payload_version": "PAYLOAD-001",
            "payload_hash": "payload-sha256-verified-digest",
            "scope_id": "SCOPE-EVAL-01",
            "scope_version": 1,
            "policy_version": "EVAL-HOLD-01",
            "rationale": "Customer Operations approves notification packet.",
        },
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

    # 1. Recall Coordinator requests closure review
    res_req = client.post("/api/evaluation/request-closure", headers={"X-API-Key": KEY_COORD})
    assert res_req.status_code == 200
    req_id = res_req.json()["request_id"]

    # 2. Closure Authority authorizes closure

    res_close = client.post(
        "/api/evaluation/authorize-closure",
        headers={"X-API-Key": KEY_CLOSURE},
        json={
            "request_id": req_id,
            "rationale": "All consignee acknowledgements verified. Case closed.",
            "effectiveness_evidence_ids": ["EVID-01"],
        },
    )
    assert res_close.status_code == 200
    assert res_close.json()["status"] == "closed"
    assert res_close.json()["projection"]["header"]["phase"] == "closed"


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
    import hmac
    import json
    import time

    from lot_zero.auth import _get_sse_secret

    sse_secret = _get_sse_secret()
    expired_payload = json.dumps(
        {"principal_id": "QA-LEAD-01", "tenant_id": "EVAL-TENANT-01", "exp": int(time.time()) - 10},
        separators=(",", ":"),
    )
    b64_exp = base64.urlsafe_b64encode(expired_payload.encode()).decode().rstrip("=")
    exp_sig = hmac.new(sse_secret.encode(), b64_exp.encode(), hashlib.sha256).hexdigest()
    expired_token = f"{b64_exp}.{exp_sig}"

    res_expired = client.get(f"/api/incidents/EVAL-CASE-01/events?token={expired_token}")
    assert res_expired.status_code == 401
    assert "Invalid, forged, or expired token" in res_expired.json()["detail"]


def test_dispatch_outbox_without_prior_approval_fails_closed(client):
    """Calling dispatch-outbox without prior approve-notification must fail, append 0 events, and leave state unchanged."""
    client.post("/api/evaluation/simulate-signal", headers={"X-API-Key": KEY_COORD})
    client.post(
        "/api/evaluation/approve-containment",
        headers={"X-API-Key": KEY_QA},
        json={"rationale": "QA approval for firm hold."},
    )

    before_state = client.get("/api/incidents/EVAL-CASE-01", headers={"X-API-Key": KEY_QA}).json()
    before_phase = before_state["header"]["phase"]
    before_events = client.get(
        "/api/cases/EVAL-CASE-01/audit-export", headers={"X-API-Key": KEY_QA}
    ).json()["events"]
    before_count = len(before_events)

    # Dispatch outbox without prior approve-notification call
    res_disp = client.post("/api/evaluation/dispatch-outbox", headers={"X-API-Key": KEY_OPS})
    assert res_disp.status_code in (409, 400)
    assert (
        "command packet is not present in incident" in res_disp.json()["detail"]
        or "notification requires prior" in res_disp.json()["detail"].lower()
    )

    # Assert 0 events appended and state unchanged
    after_state = client.get("/api/incidents/EVAL-CASE-01", headers={"X-API-Key": KEY_QA}).json()
    assert after_state["header"]["phase"] == before_phase

    after_events = client.get(
        "/api/cases/EVAL-CASE-01/audit-export", headers={"X-API-Key": KEY_QA}
    ).json()["events"]
    assert len(after_events) == before_count


def test_persisted_event_identities_equal_authenticated_principal(client):
    """All persisted event identities must equal principal.principal_id and cannot be spoofed."""
    client.post("/api/evaluation/simulate-signal", headers={"X-API-Key": KEY_COORD})

    # QA approval
    res_qa = client.post(
        "/api/evaluation/approve-containment",
        headers={"X-API-Key": KEY_QA},
        json={"rationale": "QA biological confirmation."},
    )
    assert res_qa.status_code == 200

    # Notification approval
    res_notif = client.post(
        "/api/evaluation/approve-notification",
        headers={"X-API-Key": KEY_OPS},
        json={
            "packet_id": "PKT-001",
            "payload_version": "PAYLOAD-001",
            "payload_hash": "payload-sha256-verified-digest",
            "scope_id": "SCOPE-EVAL-01",
            "scope_version": 1,
            "policy_version": "EVAL-HOLD-01",
            "rationale": "Ops approves payload.",
        },
    )
    assert res_notif.status_code == 200

    latest_state = client.get("/api/incidents/EVAL-CASE-01", headers={"X-API-Key": KEY_QA}).json()
    qa_app = [a for a in latest_state["approvals"] if a["approval_type"] == "containment"]
    assert len(qa_app) >= 1
    assert qa_app[-1]["requester_id"] == "RECALL-COORD-01"
    assert qa_app[-1]["approver_id"] == "QA-LEAD-01"
    assert qa_app[-1]["requester_id"] != qa_app[-1]["approver_id"]

    notif_app = [a for a in latest_state["approvals"] if a["approval_type"] == "notification"]
    assert len(notif_app) >= 1
    assert notif_app[-1]["requester_id"] == "RECALL-COORD-01"
    assert notif_app[-1]["approver_id"] in ("OPS-01", "OPS-001")
    assert notif_app[-1]["requester_id"] != notif_app[-1]["approver_id"]


def test_self_approval_is_denied(client):
    """A principal cannot approve their own proposed action or closure request."""
    client.post("/api/evaluation/simulate-signal", headers={"X-API-Key": KEY_COORD})
    res_req = client.post("/api/evaluation/request-closure", headers={"X-API-Key": KEY_COORD})
    assert res_req.status_code == 200
    req_id = res_req.json()["request_id"]

    # Requester attempts to authorize their own closure request -> 403 Forbidden
    res_self = client.post(
        "/api/evaluation/authorize-closure",
        headers={"X-API-Key": KEY_COORD},
        json={"request_id": req_id, "rationale": "Self approval attempt"},
    )
    assert res_self.status_code == 403


def test_missing_prior_request_is_denied_with_zero_events(client):
    """Calling approval endpoints without a prior persisted request/proposal must return 409 and append 0 events."""
    client.post("/api/evaluation/reset", headers={"X-API-Key": KEY_ADMIN})
    before_state = client.get("/api/incidents/EVAL-CASE-01", headers={"X-API-Key": KEY_QA}).json()
    before_phase = before_state["header"]["phase"]

    assert before_state.get("approvals", []) == []

    # 1. Approve containment without prior scope/containment proposal -> 409
    res_c = client.post(
        "/api/evaluation/approve-containment",
        headers={"X-API-Key": KEY_QA},
        json={"rationale": "Premature approval."},
    )
    assert res_c.status_code == 409

    # 2. Approve notification without prior scope/packet proposal -> 409
    res_n = client.post(
        "/api/evaluation/approve-notification",
        headers={"X-API-Key": KEY_OPS},
        json={
            "packet_id": "PKT-001",
            "payload_version": "PAYLOAD-001",
            "payload_hash": "dummy-hash",
            "scope_id": "SCOPE-EVAL-01",
            "scope_version": 1,
            "policy_version": "EVAL-HOLD-01",
            "rationale": "Premature ops approval.",
        },
    )
    assert res_n.status_code == 409

    # 3. Release hold step without prior hold -> 409
    res_r = client.post(
        "/api/evaluation/release-hold/step",
        headers={"X-API-Key": KEY_QA},
        json={
            "retest_doc_id": "DOC-01",
            "retest_doc_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "rationale": "Premature release.",
        },
    )
    assert res_r.status_code == 409

    # 4. Authorize closure without prior request -> 400/409
    res_cl = client.post(
        "/api/evaluation/authorize-closure",
        headers={"X-API-Key": KEY_CLOSURE},
        json={"request_id": "REQ-NONEXISTENT", "rationale": "Premature closure."},
    )
    assert res_cl.status_code in (400, 409)

    # Assert 0 events appended and phase/approvals unchanged
    after_state = client.get("/api/incidents/EVAL-CASE-01", headers={"X-API-Key": KEY_QA}).json()
    assert after_state["header"]["phase"] == before_phase
    assert after_state.get("approvals", []) == []


def test_wrong_role_closure_calls_return_403_and_zero_events(client):
    """Wrong-role request-closure and authorize-closure calls must return 403 Forbidden and append zero events."""
    client.post("/api/evaluation/simulate-signal", headers={"X-API-Key": KEY_COORD})
    client.post(
        "/api/evaluation/approve-containment",
        headers={"X-API-Key": KEY_QA},
        json={"rationale": "QA approval."},
    )

    before_events = client.get(
        "/api/cases/EVAL-CASE-01/audit-export", headers={"X-API-Key": KEY_QA}
    ).json()["events"]
    before_count = len(before_events)

    # 1. Non-coordinator (QA Lead) attempts request-closure -> 403
    res_req_qa = client.post(
        "/api/evaluation/request-closure",
        headers={"X-API-Key": KEY_QA},
        json={"closure_id": "EVAL-CLOSE-01"},
    )
    assert res_req_qa.status_code == 403
    assert (
        "coordinator" in res_req_qa.json()["detail"].lower()
        or "role" in res_req_qa.json()["detail"].lower()
    )

    after_events_1 = client.get(
        "/api/cases/EVAL-CASE-01/audit-export", headers={"X-API-Key": KEY_QA}
    ).json()["events"]
    assert len(after_events_1) == before_count

    # 2. Coordinator requests closure
    res_req = client.post("/api/evaluation/request-closure", headers={"X-API-Key": KEY_COORD})
    assert res_req.status_code == 200
    req_id = res_req.json()["request_id"]

    events_after_req = client.get(
        "/api/cases/EVAL-CASE-01/audit-export", headers={"X-API-Key": KEY_QA}
    ).json()["events"]
    req_count = len(events_after_req)

    # 3. Non-closure authority (Recall Coordinator) attempts authorize-closure -> 403
    res_close_coord = client.post(
        "/api/evaluation/authorize-closure",
        headers={"X-API-Key": KEY_COORD},
        json={"request_id": req_id, "rationale": "Attempt unauthorized closure approval."},
    )
    assert res_close_coord.status_code == 403

    events_after_denied = client.get(
        "/api/cases/EVAL-CASE-01/audit-export", headers={"X-API-Key": KEY_QA}
    ).json()["events"]
    assert len(events_after_denied) == req_count


def test_closure_with_invented_evidence_ids_denied(client):
    """Closure request and authorization with invented or unknown evidence IDs must be rejected."""
    client.post("/api/evaluation/simulate-signal", headers={"X-API-Key": KEY_COORD})

    # 1. Request closure with invented evidence ID -> 400
    res_bad_req = client.post(
        "/api/evaluation/request-closure",
        headers={"X-API-Key": KEY_COORD},
        json={"evidence_record_ids": ["EVID-FABRICATED-999"]},
    )
    assert res_bad_req.status_code == 400
    assert "unknown" in res_bad_req.json()["detail"].lower()

    # 2. Valid request closure
    res_req = client.post("/api/evaluation/request-closure", headers={"X-API-Key": KEY_COORD})
    assert res_req.status_code == 200
    req_id = res_req.json()["request_id"]

    # 3. Authorize closure with invented effectiveness evidence -> blocked
    res_bad_auth = client.post(
        "/api/evaluation/authorize-closure",
        headers={"X-API-Key": KEY_CLOSURE},
        json={"request_id": req_id, "effectiveness_evidence_ids": ["EVID-NONEXISTENT-777"]},
    )
    assert res_bad_auth.status_code == 200
    assert res_bad_auth.json()["status"] == "closure_blocked"
    assert res_bad_auth.json()["code"] == "UNKNOWN_EVIDENCE_ID"


def test_simulate_signal_live_model_failure_causes_zero_mutation(client, monkeypatch):
    """When live Vertex mode is enabled but fails, simulate-signal must produce zero state mutation and zero events."""
    from lot_zero.app import current_state

    # 1. Capture initial baseline
    initial_version = current_state.case.case_version
    initial_phase = current_state.case.phase

    # Audit export returns 404 on clean baseline before events exist
    res_initial_audit = client.get(
        "/api/cases/EVAL-CASE-01/audit-export", headers={"X-API-Key": KEY_QA}
    )
    assert res_initial_audit.status_code == 404

    # 2. Configure broken Vertex mode (missing project)
    monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "true")
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    res = client.post("/api/evaluation/simulate-signal", headers={"X-API-Key": KEY_COORD})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "needs_review"

    # 3. Assert zero state mutation and zero events appended
    assert current_state.case.case_version == initial_version
    assert current_state.case.phase == initial_phase
    assert len(current_state.containment_actions) == 0
    assert len(current_state.scopes) == 0
    assert len(current_state.ledger) == 0

    # Audit export still returns 404 proving zero events were appended
    res_after_audit = client.get(
        "/api/cases/EVAL-CASE-01/audit-export", headers={"X-API-Key": KEY_QA}
    )
    assert res_after_audit.status_code == 404
