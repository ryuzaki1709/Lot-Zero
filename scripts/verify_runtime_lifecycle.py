import os
import sys
from pathlib import Path
from datetime import UTC, datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "apps" / "api" / "src"))

from fastapi.testclient import TestClient
from lot_zero.app import app
from lot_zero.domain.audit_export import verify_audit_bundle

KEY_COORD = "key-recall-coord-01"
KEY_QA = "key-qa-lead-01"
KEY_OPS = "key-ops-01"
KEY_CLOSURE = "key-closure-auth-01"

def run_lifecycle_verification():
    print("=== STARTING END-TO-END RUNTIME VERIFICATION ===")
    with TestClient(app) as client:
        # Step 1: Clean Baseline Reset
        print("\n1. Resetting baseline...")
        res_reset = client.post("/api/evaluation/reset", headers={"X-API-Key": KEY_COORD})
        assert res_reset.status_code == 200, f"Reset failed: {res_reset.text}"
        print("[OK] Baseline reset successful")

        # Step 2: Ingest Signal & Trigger Gemini Analysis
        print("\n2. Simulating Salmonella lab safety signal...")
        res_sig = client.post("/api/evaluation/simulate-signal", headers={"X-API-Key": KEY_COORD})
        assert res_sig.status_code == 200, f"Signal simulation failed: {res_sig.text}"
        proj = res_sig.json()["projection"]
        print(f"[OK] Signal ingested. Phase: {proj['header']['phase']}, Holds: {len(proj['containment_actions'])}")

        # Step 3: Query Read-Model Projections
        print("\n3. Testing read-model projections...")
        res_all = client.get("/api/projections/cases?filter=all", headers={"X-API-Key": KEY_COORD})
        assert res_all.status_code == 200 and len(res_all.json()) >= 1
        res_open = client.get("/api/projections/cases/open-holds", headers={"X-API-Key": KEY_COORD})
        assert res_open.status_code == 200 and res_open.json()[0]["has_open_holds"] is True
        print("[OK] Read-model projections verified across tabs")

        # Step 4: QA Containment Approval
        print("\n4. QA Lead approving firm quarantine...")
        res_app = client.post(
            "/api/evaluation/approve-containment",
            headers={"X-API-Key": KEY_QA},
            json={"role": "qa", "rationale": "High CFU Salmonella confirmed by Apex Labs; firm hold required."},
        )
        assert res_app.status_code == 200
        print("[OK] QA Containment approval verified")

        # Step 5: Dispatch Consignee Outbox
        print("\n5. Customer Operations dispatching recall notices...")
        res_disp = client.post("/api/evaluation/dispatch-outbox", headers={"X-API-Key": KEY_OPS})
        assert res_disp.status_code == 200
        print("[OK] Consignee recall packets dispatched")

        # Step 6: Consignee Acknowledgement
        print("\n6. Customer Operations recording distributor phone attestation...")
        res_ack = client.post(
            "/api/evaluation/resolve-ack",
            headers={"X-API-Key": KEY_OPS},
            json={
                "caller_id": "OPS-01",
                "recipient_contact": "Warehouse Supervisor Mark Jenkins",
                "recipient_phone": "+1-555-0199",
                "call_timestamp": datetime.now(UTC).isoformat(),
                "attestation_notes": "Spoke directly with warehouse manager; confirmed 30 units placed in physical quarantine cage.",
            },
        )
        assert res_ack.status_code == 200, f"Resolve ack failed: {res_ack.text}"
        print("[OK] Distributor phone attestation recorded and verified")

        # Step 7: Dual-Signature Release Rail
        print("\n7. Executing Dual-Signature Release Rail...")
        retest_hash = "a" * 64
        # Step 7a: QA Lead biological clearance
        res_rel_qa = client.post(
            "/api/evaluation/release-hold/step",
            headers={"X-API-Key": KEY_QA},
            json={
                "retest_doc_id": "LAB-RETEST-NEG-01",
                "retest_doc_hash": retest_hash,
                "role": "qa",
                "principal_id": "QA-LEAD-01",
                "rationale": "Independent negative re-test report verified Salmonella absent.",
            },
        )
        assert res_rel_qa.status_code == 200
        print("[OK] Step 1: QA Lead biological clearance recorded")

        # Step 7b: Closure Authority operational release
        res_rel_closure = client.post(
            "/api/evaluation/release-hold/step",
            headers={"X-API-Key": KEY_CLOSURE},
            json={
                "retest_doc_id": "LAB-RETEST-NEG-01",
                "retest_doc_hash": retest_hash,
                "role": "closure_authority",
                "principal_id": "CLOSURE-AUTH-01",
                "rationale": "All biological clearance conditions satisfied; inventory un-hold authorized.",
            },
        )
        assert res_rel_closure.status_code == 200
        print("[OK] Step 2: Closure Authority operational release executed")

        # Step 8: Export Tamper-Evident Audit Bundle
        print("\n8. Exporting and cryptographically verifying audit bundle...")
        res_export = client.get("/api/cases/EVAL-CASE-01/audit-export", headers={"X-API-Key": KEY_COORD})
        assert res_export.status_code == 200
        bundle = res_export.json()
        assert bundle["event_count"] >= 4
        assert len(bundle["top_level_digest"]) == 64

        is_valid, error = verify_audit_bundle(bundle)
        assert is_valid is True, f"Audit bundle verification failed: {error}"
        print(f"[OK] Cryptographic audit bundle verified: {bundle['event_count']} events chained, root digest: {bundle['top_level_digest'][:16]}...")

    print("\n=== ALL LIFECYCLE STEPS VALIDATED AND PASSING ===")


if __name__ == "__main__":
    run_lifecycle_verification()
