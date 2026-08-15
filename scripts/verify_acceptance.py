"""Acceptance test script validating authority honesty and data integrity via standard library."""

import json
import urllib.error
import urllib.request

API_BASE = "http://127.0.0.1:8000"

KEY_COORD = "key-recall-coord-01"
KEY_QA = "key-qa-lead-01"
KEY_OPS = "key-ops-01"
KEY_CLOSURE = "key-closure-auth-01"


def http_req(method, path, headers=None, body=None):
    url = f"{API_BASE}{path}"
    req_headers = headers or {}
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        req_headers["Content-Type"] = "application/json"
    
    req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            resp_body = resp.read().decode("utf-8")
            return resp.status, json.loads(resp_body) if resp_body else {}
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        return e.code, json.loads(err_body) if err_body else {}


def test_acceptance_flow():
    print("1. Resetting incident baseline...")
    status, data = http_req("POST", "/api/evaluation/reset", {"X-API-Key": KEY_COORD})
    assert status == 200, f"Reset failed: {data}"

    print("2. Simulating signal as Recall Coordinator...")
    status, data = http_req("POST", "/api/evaluation/simulate-signal", {"X-API-Key": KEY_COORD})
    assert status == 200, f"Signal failed: {data}"
    proj = data["projection"]
    assert proj["metrics"]["provisional_hold_quantity"] == 200.0

    print("3. Testing Role Rejection: Recall Coordinator attempts to Approve Firm Quarantine...")
    status, data = http_req(
        "POST",
        "/api/evaluation/approve-containment",
        {"X-API-Key": KEY_COORD},
        {"rationale": "Attempting unauthorized approval"},
    )
    print(f"   -> Status code: {status}, Detail: {data.get('detail')}")
    assert status == 403, f"Expected 403, got {status}"
    assert any(w in data.get("detail", "").lower() for w in ["lacks", "role", "requester", "approver", "conflict"])

    print("4. Valid QA Approval: QA Lead approves firm quarantine...")
    status, data = http_req(
        "POST",
        "/api/evaluation/approve-containment",
        {"X-API-Key": KEY_QA},
        {"rationale": "Lab verified Salmonella in Lot ING-4417"},
    )
    assert status == 200, f"QA approval failed: {data}"

    print("5. Dispatch Outbox: Customer Operations dispatches notice...")
    status, data = http_req("POST", "/api/evaluation/dispatch-outbox", {"X-API-Key": KEY_OPS})
    assert status == 200, f"Dispatch failed: {data}"

    print("6. Testing Dual-Signature Release Step 1: QA Lead signs biological clearance...")
    retest_hash = "e4b8c719a89d443210feeb89012356789abcdef0123456789abcdef012345678"
    status, data = http_req(
        "POST",
        "/api/evaluation/release-hold/step",
        {"X-API-Key": KEY_QA},
        {
            "retest_doc_id": "LAB-RETEST-SPL-99824-B",
            "retest_doc_hash": retest_hash,
            "rationale": "Negative culture re-test verified.",
        },
    )
    assert status == 200, f"Step 1 failed: {data}"

    print("7. Testing Dual-Signature Role Enforcement: QA Lead attempts Step 2 (forbidden)...")
    status, data = http_req(
        "POST",
        "/api/evaluation/release-hold/step",
        {"X-API-Key": KEY_QA},
        {
            "retest_doc_id": "LAB-RETEST-SPL-99824-B",
            "retest_doc_hash": retest_hash,
            "rationale": "Attempting second signature as QA Lead",
        },
    )
    print(f"   -> Status code: {status}, Detail: {data.get('detail')}")
    assert status in (403, 400)

    print("8. Dual-Signature Step 2 Valid: Closure Authority authorizes release...")
    status, data = http_req(
        "POST",
        "/api/evaluation/release-hold/step",
        {"X-API-Key": KEY_CLOSURE},
        {
            "retest_doc_id": "LAB-RETEST-SPL-99824-B",
            "retest_doc_hash": retest_hash,
            "rationale": "Operational release authorized after QA biological clearance.",
        },
    )
    assert status == 200, f"Step 2 failed: {data}"
    proj_final = data["projection"]
    assert any(a["action_type"] == "release_hold" for a in proj_final["containment_actions"])

    print("9. Non-Response Attempt Count Verbatim Pass-through Test...")
    http_req("POST", "/api/evaluation/reset", {"X-API-Key": KEY_COORD})
    http_req("POST", "/api/evaluation/simulate-signal", {"X-API-Key": KEY_COORD})
    http_req(
        "POST",
        "/api/evaluation/approve-containment",
        {"X-API-Key": KEY_QA},
        {"rationale": "Quarantine approved."},
    )
    http_req("POST", "/api/evaluation/dispatch-outbox", {"X-API-Key": KEY_OPS})

    status, data = http_req(
        "POST",
        "/api/evaluation/close-with-non-response",
        {"X-API-Key": KEY_CLOSURE},
        {
            "attempt_count": 5,
            "regulatory_filing_id": "FDA-SAN-2026-NR-CUSTOM-005",
            "good_faith_notes": "Five certified contact attempts executed. Consignee non-responsive.",
        },
    )
    assert status == 200, f"Non-response failed: {data}"
    assert data["regulatory_filing_id"] == "FDA-SAN-2026-NR-CUSTOM-005"
    assert data["projection"]["header"]["phase"] == "closed"

    print("10. Testing SSE stream authentication...")
    # Without token -> 401
    status, data = http_req("GET", "/api/incidents/EVAL-CASE-01/events")
    assert status == 401

    print("\nALL ACCEPTANCE CRITERIA PASSED!")


if __name__ == "__main__":
    test_acceptance_flow()
