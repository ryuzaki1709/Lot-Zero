import os

os.environ["LOT_ZERO_EVALUATION_MODE"] = "true"

import asyncio
from httpx import ASGITransport, AsyncClient
from lot_zero.app import app

from lot_zero.domain.projections import CaseSummaryProjection


async def verify_sync_lifecycle():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        results = []

        async def check_step(step_name: str, endpoint: str, method: str, key: str, json_body=None):
            headers = {"X-API-Key": key}
            if method == "POST":
                r = await client.post(endpoint, headers=headers, json=json_body)
            else:
                r = await client.get(endpoint, headers=headers)
            assert r.status_code == 200, f"{step_name} failed: {r.status_code} {r.text}"
            data = r.json()
            proj = data.get("projection")
            main_ver = proj["header"]["case_version"] if proj else "N/A"
            main_phase = proj["header"]["phase"] if proj else "N/A"

            # Query read-model projections endpoint as the incident card does
            card_res = await client.get("/api/projections/cases?filter=all", headers={"X-API-Key": key})
            assert card_res.status_code == 200, f"Card fetch failed: {card_res.status_code}"
            card_data = card_res.json()
            assert len(card_data) > 0, f"No card returned for {step_name}"
            card_ver = card_data[0]["case_version"]
            card_phase = card_data[0]["phase"]

            match = (main_ver == card_ver) and (main_phase == card_phase)
            results.append({
                "step": step_name,
                "main_ver": main_ver,
                "main_phase": main_phase,
                "card_ver": card_ver,
                "card_phase": card_phase,
                "match": match,
                "data": data,
            })
            return data

        # 1. Reset
        await check_step("1. Reset", "/api/evaluation/reset", "POST", "key-eval-admin-01")

        # 2. Signal Simulation
        await check_step("2. Signal Simulation", "/api/evaluation/simulate-signal", "POST", "key-recall-coord-01")

        # 3. QA Approval
        await check_step("3. QA Containment Approval", "/api/evaluation/approve-containment", "POST", "key-qa-lead-01", {"rationale": "Salmonella confirmed."})

        # 4. Notification Request
        await check_step("4. Notification Request", "/api/evaluation/request-notification", "POST", "key-recall-coord-01", {
            "packet_id": "PKT-001",
            "scope_id": "SCOPE-EVAL-01",
            "scope_version": 1,
            "payload_version": "PAYLOAD-001",
            "payload_hash": "payload-sha256-verified-digest",
            "policy_version": "EVAL-HOLD-01",
        })

        # 5. Notification Approval
        await check_step("5. Notification Approval", "/api/evaluation/approve-notification", "POST", "key-ops-01", {
            "packet_id": "PKT-001",
            "scope_id": "SCOPE-EVAL-01",
            "scope_version": 1,
            "payload_version": "PAYLOAD-001",
            "payload_hash": "payload-sha256-verified-digest",
            "policy_version": "EVAL-HOLD-01",
            "rationale": "Approved notice payload.",
        })

        # 6. Dispatch
        await check_step("6. Outbox Dispatch", "/api/evaluation/dispatch-outbox", "POST", "key-ops-01")

        # 7. Closure Request
        req_res = await check_step("7. Closure Request", "/api/evaluation/request-closure", "POST", "key-recall-coord-01")
        req_id = req_res.get("request_id")

        # 8. ACK Resolution
        await check_step("8. ACK Resolution", "/api/evaluation/resolve-ack", "POST", "key-ops-01", {
            "caller_id": "OPS-001",
            "recipient_contact": "David Miller",
            "recipient_phone": "+1 612 555 0194",
            "call_timestamp": "2026-08-22T08:00:00Z",
            "attestation_notes": "All units dock quarantined.",
        })

        # 9. Final Closure
        await check_step("9. Final Closure", "/api/evaluation/authorize-closure", "POST", "key-closure-auth-01", {"request_id": req_id})

        print("\n" + "="*80)
        print(f"{'STEP':<30} | {'MAIN PROJECTION':<20} | {'INCIDENT CARD':<20} | {'MATCH'}")
        print("="*80)
        all_matched = True
        for r in results:
            main_str = f"v{r['main_ver']} · {r['main_phase']}"
            card_str = f"v{r['card_ver']} · {r['card_phase']}"
            matched = "YES [PASS]" if r["match"] else "NO [FAIL]"
            if not r["match"]:
                all_matched = False
            print(f"{r['step']:<30} | {main_str:<20} | {card_str:<20} | {matched}")
        print("="*80)
        assert all_matched, "Not all steps matched between main projection and incident card!"
        print(">>> ALL 9 LIFECYCLE STEPS ARE PERFECTLY SYNCHRONIZED! <<<\n")


if __name__ == "__main__":
    asyncio.run(verify_sync_lifecycle())
