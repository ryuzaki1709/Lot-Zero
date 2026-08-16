"""Remote smoke-test script for Cloud Run deployment of Lot Zero.

Usage:
    python scripts/verify_cloud_deploy.py [SERVICE_URL]

Example:
    python scripts/verify_cloud_deploy.py https://lot-zero-xyz-uc.a.run.app
"""

import json
import sys
import urllib.error
import urllib.request
import hashlib

DEFAULT_URL = "http://127.0.0.1:8000"
SERVICE_URL = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URL

KEY_COORD = "key-recall-coord-01"
KEY_QA = "key-qa-lead-01"
KEY_OPS = "key-ops-01"
KEY_CLOSURE = "key-closure-auth-01"


def http_req(method, path, headers=None, body=None):
    url = f"{SERVICE_URL.rstrip('/')}{path}"
    req_headers = headers or {}
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        req_headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            resp_body = resp.read().decode("utf-8")
            return resp.status, json.loads(resp_body) if resp_body.startswith(("{", "[")) else resp_body
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        try:
            return e.code, json.loads(err_body)
        except Exception:
            return e.code, err_body


def verify_cloud_deployment():
    print(f"================================================================")
    print(f" LOT ZERO CLOUD RUN SMOKE TEST & PROOF VERIFICATION")
    print(f" Target Service: {SERVICE_URL}")
    print(f"================================================================\n")

    # 1. Verify Root SPA serves HTML
    print("1. Checking SPA static asset hosting on Cloud Run...")
    status, body = http_req("GET", "/")
    assert status == 200, f"Root SPA returned status {status}"
    assert "<!doctype html>" in body.lower() or "<html" in body.lower(), "Root SPA did not return HTML"
    print("   [PASS] Root SPA serves bundled Vite frontend.")

    # 2. Reset baseline
    print("2. Resetting incident state to baseline...")
    status, data = http_req("POST", "/api/evaluation/reset", {"X-API-Key": KEY_COORD})
    assert status == 200, f"Reset failed: {data}"
    print("   [PASS] Reset incident state.")

    # 3. Simulate Signal via Gemini on Vertex AI
    print("3. Executing safety signal extraction via Gemini on Vertex AI...")
    status, data = http_req("POST", "/api/evaluation/simulate-signal", {"X-API-Key": KEY_COORD})
    assert status == 200, f"Simulate signal failed: {data}"
    model_val = data["projection"]["runtime"]["model"]["value"]
    assert "Replay" not in model_val, f"Live Gemini 3.5 call failed — model tag contains 'Replay': {model_val}"
    assert model_val.startswith("gemini-3.5"), f"Expected gemini-3.5 model, got {model_val}"
    assert "(Vertex AI Live)" in model_val or "(Gemini API Live)" in model_val, f"Expected live execution tag, got {model_val}"

    # 4. Wrong-role refusal: Recall Coordinator attempts QA quarantine approval
    print("4. Testing Separation of Duties (wrong-role denial)...")
    status, data = http_req(
        "POST",
        "/api/evaluation/approve-containment",
        {"X-API-Key": KEY_COORD},
        {"rationale": "Unauthorized coordinator attempt"},
    )
    print(f"   -> Status Code: {status}, Detail: {data.get('detail') if isinstance(data, dict) else data}")
    assert status == 403, f"Expected 403 Forbidden, got {status}"
    print("   [PASS] Server enforced 403 refusal on unauthorized role.")

    # 5. Legitimate QA approval
    print("5. Submitting authorized QA Lead quarantine approval...")
    status, data = http_req(
        "POST",
        "/api/evaluation/approve-containment",
        {"X-API-Key": KEY_QA},
        {"rationale": "Salmonella contamination confirmed in Lot ING-4417"},
    )
    assert status == 200, f"QA approval failed: {data}"
    print("   [PASS] QA Lead quarantine authorized.")

    # 6. Dispatch outbox
    print("6. Customer Operations dispatches recall outbox...")
    status, data = http_req("POST", "/api/evaluation/dispatch-outbox", {"X-API-Key": KEY_OPS})
    assert status == 200, f"Dispatch failed: {data}"
    print("   [PASS] Recall notices dispatched.")

    # 7. Audit export & Hash chain verification
    print("7. Exporting cryptographic audit bundle and verifying hash chain...")
    status, bundle = http_req("GET", "/api/cases/EVAL-CASE-01/audit-export", {"X-API-Key": KEY_QA})
    assert status == 200, f"Audit export failed: {bundle}"
    assert bundle["tenant_id"] == "EVAL-TENANT-01"
    assert bundle["case_id"] == "EVAL-CASE-01"
    
    events = bundle["events"]
    print(f"   -> Total Ledger Entries: {len(events)}")
    assert len(events) > 0, "No audit events found in export"
    
    # Verify unbroken hash chain
    expected_prior_hash = None
    for i, ev in enumerate(events, start=1):
        assert ev["sequence"] == i, f"Sequence discontinuity at index {i}"
        assert ev["prior_entry_hash"] == expected_prior_hash, f"Hash chain linkage mismatch at sequence {i}"
        
        # Verify entry hash: f"{sequence}:{event_type}:{payload_hash}:{prior_entry_hash or ''}:{occurred_at}"
        raw_entry = f"{ev['sequence']}:{ev['event_type']}:{ev['payload_hash']}:{ev['prior_entry_hash'] or ''}:{ev['occurred_at']}"
        computed_entry_hash = hashlib.sha256(raw_entry.encode("utf-8")).hexdigest()
        assert ev["entry_hash"] == computed_entry_hash, f"Entry hash tampering detected at sequence {i}"
        expected_prior_hash = ev["entry_hash"]
        
    # Verify root digest
    raw_root = f"{bundle['tenant_id']}:{bundle['case_id']}:{bundle['event_count']}:{expected_prior_hash or 'GENESIS'}"
    computed_root = hashlib.sha256(raw_root.encode("utf-8")).hexdigest()
    assert bundle["top_level_digest"] == computed_root, "Top-level root digest mismatch"
    print(f"   -> Top-Level Digest: {bundle['top_level_digest']}")
    print("   [PASS] Cryptographic audit hash chain 100% verified.")

    print("\n================================================================")
    print(" ALL CLOUD RUN DEPLOYMENT CHECKS & PROOFS PASSED!")
    print("================================================================\n")


if __name__ == "__main__":
    verify_cloud_deployment()
