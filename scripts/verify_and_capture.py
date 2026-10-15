"""Browser regression verification and portfolio screenshot capture script.

Exercises:
1. Scenario A: Normal browser storage
2. Scenario B: Local storage getter throwing SecurityError
3. Scenario C: Storage methods (getItem, setItem, removeItem) throwing exceptions
4. Scenario D: Initial /api/config failure with disabled controls and explicit Retry Connection recovery
5. Meaningful screenshot capture with explicit bounding-box assertions:
   - 01: Grounded evidence citations and affected vs clean genealogy (verifying FP-100-ADJ clean batch inside captured region)
   - 02: Blocked closure gate on ACK-006 and role approval controls (verifying closure blocked message and ACK-006 pending inside captured region)
   - 03: Reconciled approvals, phone attestation SHA-256 hash, outbox (6 of 6 confirmed), and verified JSON audit bundle export
6. Safe process management: isolated temporary database, verification of launched process.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Any

from playwright.sync_api import Browser, Locator, Page, sync_playwright

ROOT = Path(__file__).resolve().parent.parent
IMAGES_DIR = ROOT / "docs" / "images"
IMAGES_DIR.mkdir(parents=True, exist_ok=True)


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_for_server(url: str, timeout: float = 15.0) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(f"{url}/api/health", timeout=1.0) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.3)
    return False


def assert_element_in_captured_region(
    locator: Locator,
    viewport_width: int,
    viewport_height: int,
    name: str = "element",
) -> None:
    """Assert that the element's bounding rect is fully contained within the captured viewport region."""
    box = locator.evaluate(
        """(el) => {
            const rect = el.getBoundingClientRect();
            return {
                x: rect.x,
                y: rect.y,
                width: rect.width,
                height: rect.height,
                top: rect.top,
                bottom: rect.bottom,
                left: rect.left,
                right: rect.right,
            };
        }"""
    )
    assert box is not None, f"Element '{name}' has no bounding box (not rendered in DOM)!"
    # Allow 1.0px tolerance for browser subpixel anti-aliasing / floating-point rounding
    assert box["top"] >= -1.0, (
        f"Element '{name}' top ({box['top']:.1f}px) is cut off above captured region (top < 0)"
    )
    assert box["bottom"] <= viewport_height + 1.0, (
        f"Element '{name}' bottom ({box['bottom']:.1f}px) is cut off below captured region (> {viewport_height}px)"
    )
    assert box["left"] >= -1.0, (
        f"Element '{name}' left ({box['left']:.1f}px) is left of captured region"
    )
    assert box["right"] <= viewport_width + 1.0, (
        f"Element '{name}' right ({box['right']:.1f}px) is right of captured region"
    )
    print(
        f"    [BOUNDING-BOX OK] {name}: y=[{box['top']:.1f}, {box['bottom']:.1f}] inside [0, {viewport_height}]"
    )


# ---------------------------------------------------------------------------
# Task 3: Repair Browser Regression Tests (Independent Contexts)
# ---------------------------------------------------------------------------


def run_scenario_a_normal_storage(browser: Browser, base_url: str) -> None:
    """Scenario A: Standard browser with normal localStorage access."""
    print("\n--- Running Scenario A: Normal Storage ---")
    context = browser.new_context(viewport={"width": 1440, "height": 1000})
    page = context.new_page()

    page_errors: list[str] = []
    page.on("pageerror", lambda err: page_errors.append(str(err)))

    authenticated_keys: list[str] = []
    sse_token_received = False
    incident_payload: dict[str, Any] = {}

    def handle_request(req):
        if "/api/" in req.url:
            auth_key = req.headers.get("x-api-key")
            if auth_key:
                authenticated_keys.append(auth_key)

    def handle_response(resp):
        nonlocal sse_token_received, incident_payload
        if "/api/sse-token" in resp.url and resp.status == 200:
            sse_token_received = True
        if "/api/incidents/" in resp.url and resp.status == 200:
            try:
                incident_payload = resp.json()
            except Exception:
                pass

    page.on("request", handle_request)
    page.on("response", handle_response)

    page.goto(base_url, wait_until="networkidle")

    # Assert expected persona selected
    page.wait_for_selector('select[aria-label="Evaluation Persona Selector"]', timeout=6000)
    persona_select = page.locator('select[aria-label="Evaluation Persona Selector"]')
    assert persona_select.input_value() == "key-recall-coord-01", (
        f"Expected Recall Coordinator, got {persona_select.input_value()}"
    )
    assert "Recall Coordinator" in page.locator(".topbar").inner_text()

    # Assert incident projection response was received and rendered in UI (not relying on static fallback case ID)
    assert bool(incident_payload), "Expected successful /api/incidents/ response in Scenario A"
    source_id = incident_payload.get("signal", {}).get("source_id")
    assert source_id, "Expected signal.source_id in incident projection response"
    page.wait_for_selector(f'text="{source_id}"', timeout=6000)
    assert page.locator(f'text="{source_id}"').first.is_visible()

    # Assert authenticated request uses selected persona
    assert "key-recall-coord-01" in authenticated_keys, (
        f"No requests with expected persona key: {authenticated_keys}"
    )

    # Assert /api/sse-token succeeds and SSE indicator turns connected
    assert sse_token_received, "Expected successful /api/sse-token response"
    page.wait_for_selector('.status-inline:has-text("Live")', timeout=8000)
    assert page.locator('.status-inline:has-text("Live")').first.is_visible()

    # Assert no unexpected page errors
    assert len(page_errors) == 0, f"Unexpected page errors in Scenario A: {page_errors}"
    print("  [PASS] Scenario A: Normal storage, projection, auth, and SSE verified.")
    context.close()


def run_scenario_b_storage_getter_throws(browser: Browser, base_url: str) -> None:
    """Scenario B: window.localStorage getter throws SecurityError (sandboxed iframe / partitioned storage)."""
    print("\n--- Running Scenario B: localStorage Getter Throws SecurityError ---")
    context = browser.new_context(viewport={"width": 1440, "height": 1000})
    context.add_init_script("""
        Object.defineProperty(window, 'localStorage', {
            get: () => {
                throw new DOMException('Access to storage denied', 'SecurityError');
            },
            configurable: true
        });
    """)
    page = context.new_page()

    page_errors: list[str] = []
    page.on("pageerror", lambda err: page_errors.append(str(err)))

    authenticated_keys: list[str] = []
    sse_token_received = False
    incident_payload: dict[str, Any] = {}

    def handle_request(req):
        if "/api/" in req.url:
            auth_key = req.headers.get("x-api-key")
            if auth_key:
                authenticated_keys.append(auth_key)

    def handle_response(resp):
        nonlocal sse_token_received, incident_payload
        if "/api/sse-token" in resp.url and resp.status == 200:
            sse_token_received = True
        if "/api/incidents/" in resp.url and resp.status == 200:
            try:
                incident_payload = resp.json()
            except Exception:
                pass

    page.on("request", handle_request)
    page.on("response", handle_response)

    # Demonstrate that accessing window.localStorage genuinely throws SecurityError
    page.goto(base_url, wait_until="commit")
    threw = page.evaluate("""() => {
        try {
            const x = window.localStorage;
            return false;
        } catch (e) {
            return e.name === 'SecurityError';
        }
    }""")
    assert threw, "window.localStorage getter did not throw SecurityError as expected"

    page.wait_for_load_state("networkidle")

    # Assert app initialized with React in-memory fallback
    page.wait_for_selector('select[aria-label="Evaluation Persona Selector"]', timeout=6000)
    persona_select = page.locator('select[aria-label="Evaluation Persona Selector"]')
    assert persona_select.input_value() == "key-recall-coord-01"
    topbar_text = page.locator(".topbar").inner_text()
    assert "Recall Coordinator" in topbar_text
    assert "Sign-in / API Key Required" not in topbar_text

    # Assert incident projection response was received and rendered in UI
    assert bool(incident_payload), "Expected successful /api/incidents/ response in Scenario B"
    source_id = incident_payload.get("signal", {}).get("source_id")
    assert source_id, "Expected signal.source_id in incident projection response"
    page.wait_for_selector(f'text="{source_id}"', timeout=6000)
    assert page.locator(f'text="{source_id}"').first.is_visible()

    # Assert authenticated request uses selected persona from in-memory state
    assert "key-recall-coord-01" in authenticated_keys

    # Assert SSE token and connection
    assert sse_token_received, "Expected successful /api/sse-token response"
    page.wait_for_selector('.status-inline:has-text("Live")', timeout=8000)
    assert page.locator('.status-inline:has-text("Live")').first.is_visible()

    assert len(page_errors) == 0, f"Unexpected page errors in Scenario B: {page_errors}"
    print("  [PASS] Scenario B: Storage getter SecurityError safely handled via React in-memory state.")
    context.close()


def run_scenario_c_storage_methods_throw(browser: Browser, base_url: str) -> None:
    """Scenario C: Storage methods (getItem, setItem, removeItem) throw SecurityError."""
    print("\n--- Running Scenario C: localStorage Methods Throw SecurityError ---")
    context = browser.new_context(viewport={"width": 1440, "height": 1000})
    context.add_init_script("""
        Object.defineProperty(window, 'localStorage', {
            value: {
                getItem: (k) => { throw new DOMException('getItem denied', 'SecurityError'); },
                setItem: (k, v) => { throw new DOMException('setItem denied', 'SecurityError'); },
                removeItem: (k) => { throw new DOMException('removeItem denied', 'SecurityError'); },
                clear: () => { throw new DOMException('clear denied', 'SecurityError'); },
                length: 0,
                key: () => null,
            },
            configurable: true
        });
    """)
    page = context.new_page()

    page_errors: list[str] = []
    page.on("pageerror", lambda err: page_errors.append(str(err)))

    authenticated_keys: list[str] = []
    sse_token_received = False
    incident_payload: dict[str, Any] = {}

    def handle_request(req):
        if "/api/" in req.url:
            auth_key = req.headers.get("x-api-key")
            if auth_key:
                authenticated_keys.append(auth_key)

    def handle_response(resp):
        nonlocal sse_token_received, incident_payload
        if "/api/sse-token" in resp.url and resp.status == 200:
            sse_token_received = True
        if "/api/incidents/" in resp.url and resp.status == 200:
            try:
                incident_payload = resp.json()
            except Exception:
                pass

    page.on("request", handle_request)
    page.on("response", handle_response)

    page.goto(base_url, wait_until="commit")

    # Demonstrate that the storage methods ACTUALLY throw before asserting app handles them
    verify_throws = page.evaluate("""() => {
        let threwGet = false;
        let threwSet = false;
        let threwRemove = false;
        try { window.localStorage.getItem('test'); } catch (e) { threwGet = e.name === 'SecurityError'; }
        try { window.localStorage.setItem('test', '1'); } catch (e) { threwSet = e.name === 'SecurityError'; }
        try { window.localStorage.removeItem('test'); } catch (e) { threwRemove = e.name === 'SecurityError'; }
        return threwGet && threwSet && threwRemove;
    }""")
    assert verify_throws, "localStorage methods did not throw SecurityError as expected"

    page.wait_for_load_state("networkidle")

    # Assert expected persona selected
    page.wait_for_selector('select[aria-label="Evaluation Persona Selector"]', timeout=6000)
    persona_select = page.locator('select[aria-label="Evaluation Persona Selector"]')
    assert persona_select.input_value() == "key-recall-coord-01"
    topbar_text = page.locator(".topbar").inner_text()
    assert "Recall Coordinator" in topbar_text
    assert "Sign-in / API Key Required" not in topbar_text

    # Assert incident projection loaded and rendered in UI
    assert bool(incident_payload), "Expected successful /api/incidents/ response in Scenario C"
    source_id = incident_payload.get("signal", {}).get("source_id")
    assert source_id, "Expected signal.source_id in incident response"
    page.wait_for_selector(f'text="{source_id}"', timeout=6000)
    assert page.locator(f'text="{source_id}"').first.is_visible()

    # Assert authenticated request uses selected persona
    assert "key-recall-coord-01" in authenticated_keys

    # Assert /api/sse-token and SSE stream connection
    assert sse_token_received, "Expected successful /api/sse-token response"
    page.wait_for_selector('.status-inline:has-text("Live")', timeout=8000)
    assert page.locator('.status-inline:has-text("Live")').first.is_visible()

    assert len(page_errors) == 0, f"Unexpected page errors in Scenario C: {page_errors}"
    print("  [PASS] Scenario C: Throwing storage methods verified and safely bypassed.")
    context.close()


def run_scenario_d_config_failure_and_retry(browser: Browser, base_url: str) -> None:
    """Scenario D: /api/config failure displays fail-closed alert with disabled controls, and Retry recovers."""
    print("\n--- Running Scenario D: Config Failure -> Disabled Controls -> Retry Recovery ---")
    context = browser.new_context(viewport={"width": 1440, "height": 1000})
    page = context.new_page()

    page_errors: list[str] = []
    page.on("pageerror", lambda err: page_errors.append(str(err)))

    should_fail = True
    incident_payload: dict[str, Any] = {}

    def handle_config_route(route):
        nonlocal should_fail
        if should_fail:
            route.fulfill(
                status=500,
                body=json.dumps({"detail": "Simulated configuration service outage"}),
                headers={"content-type": "application/json"},
            )
        else:
            route.continue_()

    def handle_response(resp):
        nonlocal incident_payload
        if "/api/incidents/" in resp.url and resp.status == 200:
            try:
                incident_payload = resp.json()
            except Exception:
                pass

    page.on("response", handle_response)
    page.route("**/api/config", handle_config_route)
    page.goto(base_url, wait_until="networkidle")

    # 1. Assert fail-closed alert is visible
    page.wait_for_selector('[role="alert"]', timeout=6000)
    alert = page.locator('[role="alert"]')
    assert "Configuration Service Offline" in alert.inner_text()
    retry_btn = page.locator('button:has-text("Retry Connection")')
    assert retry_btn.first.is_visible()

    # 2. Assert operational controls are disabled during config failure
    # Header action buttons (e.g., Simulate signal or Reset state) must be disabled
    action_buttons = page.locator(".topbar-actions button.btn")
    count = action_buttons.count()
    assert count > 0, "No action buttons found in header"
    for idx in range(count):
        btn = action_buttons.nth(idx)
        # Skip the 'Docs' / architecture notes guide button which is purely informational
        if "Docs" in btn.inner_text() or "How it works" in btn.inner_text():
            continue
        assert btn.is_disabled(), f"Button '{btn.inner_text()}' was not disabled during config failure"
    print("  [PASS] Controls are properly disabled during config failure.")

    # 3. Simulate server recovery and click Retry Connection
    print("Clicking 'Retry Connection'...")
    should_fail = False
    retry_btn.click()

    # 4. Assert alert detaches and operational state recovers
    page.wait_for_selector('[role="alert"]', state="detached", timeout=8000)
    page.wait_for_selector('select[aria-label="Evaluation Persona Selector"]', timeout=6000)
    persona_select = page.locator('select[aria-label="Evaluation Persona Selector"]')
    assert persona_select.input_value() == "key-recall-coord-01"

    # Assert incident projection loads upon recovery and renders response value in UI
    if not incident_payload:
        page.wait_for_response(lambda r: "/api/incidents/" in r.url and r.status == 200, timeout=8000)
    assert bool(incident_payload), "Expected successful /api/incidents/ response after retry in Scenario D"
    source_id = incident_payload.get("signal", {}).get("source_id")
    assert source_id, "Expected signal.source_id in incident response"
    page.wait_for_selector(f'text="{source_id}"', timeout=6000)
    assert page.locator(f'text="{source_id}"').first.is_visible()

    # Assert SSE connects
    page.wait_for_selector('.status-inline:has-text("Live")', timeout=8000)
    assert page.locator('.status-inline:has-text("Live")').first.is_visible()

    assert len(page_errors) == 0, f"Unexpected page errors in Scenario D: {page_errors}"
    print("  [PASS] Scenario D: Recovered operational state via explicit Retry Connection.")
    context.close()


# ---------------------------------------------------------------------------
# Task 4: Capture Meaningful Portfolio Screenshots with Bounding Box Proofs
# ---------------------------------------------------------------------------


def capture_screenshots_and_verify_export(browser: Browser, base_url: str) -> None:
    print("\n--- Capturing Meaningful Portfolio Screenshots with Bounding Box Proofs ---")

    # Sizing for readable LinkedIn presentation and full card capture
    viewport_w = 1440
    viewport_h = 1500

    context = browser.new_context(viewport={"width": viewport_w, "height": viewport_h})
    page = context.new_page()

    page.goto(base_url, wait_until="networkidle")
    page.wait_for_selector(".topbar", timeout=6000)

    persona_select = page.locator('select[aria-label="Evaluation Persona Selector"]')
    persona_select.select_option("key-recall-coord-01")
    page.wait_for_selector('.status-inline:has-text("Live")', timeout=8000)

    # -------------------------------------------------------------------------
    # Screenshot 1: Grounded Evidence & Affected vs Clean Genealogy
    # -------------------------------------------------------------------------
    print("\n[Step 1] Simulating lab safety signal...")
    simulate_btn = page.locator('button:has-text("Simulate signal")')
    simulate_btn.click()

    # Wait for grounded signal and genealogy DAG to render
    page.wait_for_selector('text="ING-4417"', timeout=8000)
    page.wait_for_selector('text="FP-100-ADJ"', timeout=8000)

    # Scroll cockpit columns to top to frame evidence and genealogy cleanly
    page.evaluate("() => document.querySelector('main.cockpit-grid').scrollIntoView(true)")
    page.wait_for_timeout(600)

    # Bounding-box assertions: prove affected AND clean control batches are completely within the captured image
    print("Verifying Screenshot 1 bounding boxes:")
    assert_element_in_captured_region(
        page.locator('text=/Contaminated Lot.*EVID-01/i').first, viewport_w, viewport_h, "Citation Badge (EVID-01)"
    )
    assert_element_in_captured_region(
        page.locator('text=/Raw Ingredient Lot ING-4417/i').first, viewport_w, viewport_h, "Verbatim Notice Highlight"
    )
    assert_element_in_captured_region(
        page.locator('text="FP-100-L240814-A"').first, viewport_w, viewport_h, "Downstream Batch A"
    )
    assert_element_in_captured_region(
        page.locator('text="FP-100-L240814-B"').first, viewport_w, viewport_h, "Downstream Batch B"
    )
    assert_element_in_captured_region(
        page.locator('text="FP-100-ADJ"').first, viewport_w, viewport_h, "Clean Negative Control (FP-100-ADJ)"
    )
    assert_element_in_captured_region(
        page.locator('text=/Verified negative — released/i').first, viewport_w, viewport_h, "Clean Batch Status"
    )

    path1 = IMAGES_DIR / "01_grounded_evidence_and_genealogy.png"
    page.screenshot(path=str(path1), full_page=False)
    print(f"  [SAVED] {path1.name} ({path1.stat().st_size} bytes)")

    # -------------------------------------------------------------------------
    # Advance Workflow: Quarantine -> Notice Request -> Approval -> Outbox
    # -------------------------------------------------------------------------
    print("\nAdvancing workflow: QA Lead approves firm quarantine...")
    persona_select.select_option("key-qa-lead-01")
    page.wait_for_selector('button:has-text("Approve Firm Quarantine")', timeout=5000)
    page.locator('button:has-text("Approve Firm Quarantine")').click()
    page.wait_for_selector('text="Quarantine Approved (QA)"', timeout=8000)

    print("Recall Coordinator requests notification packet...")
    persona_select.select_option("key-recall-coord-01")
    page.wait_for_selector('button:has-text("Request Notification Packet")', timeout=5000)
    page.locator('button:has-text("Request Notification Packet")').click()
    page.wait_for_selector('text="Packet PKT-001 Requested"', timeout=8000)

    print("Customer Operations approves notification packet...")
    persona_select.select_option("key-ops-01")
    page.wait_for_selector('button:has-text("Approve Notification Packet")', timeout=5000)
    page.locator('button:has-text("Approve Notification Packet")').click()
    page.wait_for_selector('text="Notification Approved (Ops)"', timeout=8000)

    print("Customer Operations dispatches recall outbox...")
    page.wait_for_selector('button:has-text("Dispatch Recall Outbox")', timeout=5000)
    page.locator('button:has-text("Dispatch Recall Outbox")').click()
    page.wait_for_selector('text="Outbox Dispatched"', timeout=8000)

    # -------------------------------------------------------------------------
    # Screenshot 2: Blocked Closure Gate on ACK-006 & Role Approvals
    # -------------------------------------------------------------------------
    print("Recall Coordinator requests case closure -> triggering blocked gate...")
    persona_select.select_option("key-recall-coord-01")
    page.wait_for_selector('button:has-text("Request Case Closure")', timeout=5000)
    page.locator('button:has-text("Request Case Closure")').click()

    # Wait for closure blocked message to appear
    page.wait_for_selector('text=/Closure blocked/i', timeout=8000)
    page.wait_for_selector('text="ACK-006"', timeout=8000)

    # Scroll so ACK-006 in outbox and Gate 6b blocker callout are both framed within the captured viewport
    ack_el = page.locator('text="ACK-006"').first
    doc_y_ack = ack_el.evaluate("el => el.getBoundingClientRect().top + window.scrollY")
    page.evaluate(f"() => window.scrollTo(0, {doc_y_ack - 50})")
    page.wait_for_timeout(600)

    print("Verifying Screenshot 2 bounding boxes:")
    assert_element_in_captured_region(
        page.locator('text=/Closure blocked: Unverified/i').first, viewport_w, viewport_h, "Closure Blocked Status"
    )
    assert_element_in_captured_region(
        page.locator('text="3. Verify Consignee Attestation"').first, viewport_w, viewport_h, "Gate 3: Consignee Attestation"
    )
    assert_element_in_captured_region(
        page.locator('button:has-text("Verify Phone Attestation")').first, viewport_w, viewport_h, "Verify Phone Button"
    )
    assert_element_in_captured_region(
        page.locator('text="6b. Authorize Incident Closure"').first, viewport_w, viewport_h, "Gate 6b: Authorize Closure"
    )
    assert_element_in_captured_region(
        page.locator('text="ACK-006"').first, viewport_w, viewport_h, "Consignee ACK-006"
    )
    assert_element_in_captured_region(
        page.locator('text="Pending"').first, viewport_w, viewport_h, "ACK-006 Pending Status"
    )

    path2 = IMAGES_DIR / "02_blocked_closure_and_role_approvals.png"
    page.screenshot(path=str(path2), full_page=False)
    print(f"  [SAVED] {path2.name} ({path2.stat().st_size} bytes)")

    # -------------------------------------------------------------------------
    # Resolve ACK-006 via Phone Attestation -> Authorize Final Closure
    # -------------------------------------------------------------------------
    print("\nCustomer Operations logs signed phone attestation for ACK-006...")
    persona_select.select_option("key-ops-01")
    page.wait_for_selector('button:has-text("Verify Phone Attestation")', timeout=5000)
    page.locator('button:has-text("Verify Phone Attestation")').click()

    page.wait_for_selector('button:has-text("Sign & Record Attestation")', timeout=5000)
    page.locator('button:has-text("Sign & Record Attestation")').click()
    page.wait_for_selector('text="Signed phone attestation attached"', timeout=8000)

    print("Closure Authority authorizes final case closure...")
    persona_select.select_option("key-closure-auth-01")
    page.wait_for_selector('button:has-text("Authorize Final Closure")', timeout=5000)
    page.locator('button:has-text("Authorize Final Closure")').click()

    page.wait_for_selector('text=/Incident disposition complete/i', timeout=8000)

    # -------------------------------------------------------------------------
    # Download and Cryptographically Verify Audit Export Bundle JSON
    # -------------------------------------------------------------------------
    print("Testing Audit Export download and verifying JSON contents...")
    with page.expect_download() as download_info:
        export_btn = page.locator('button[title*="audit bundle"]')
        export_btn.click()

    download = download_info.value
    downloaded_path = ROOT / "docs" / "audit_export_verification.json"
    download.save_as(str(downloaded_path))

    with open(downloaded_path, "r", encoding="utf-8") as f:
        export_data = json.load(f)

    from lot_zero.domain.audit_export import verify_audit_bundle

    is_valid, error_msg = verify_audit_bundle(export_data)
    assert is_valid, f"Audit export verification failed: {error_msg}"

    assert export_data["case_id"] == "EVAL-CASE-01"
    assert "top_level_digest" in export_data and len(export_data["top_level_digest"]) == 64
    assert export_data["event_count"] > 0
    assert len(export_data["events"]) == export_data["event_count"]
    for ev in export_data["events"]:
        assert "entry_hash" in ev and len(ev["entry_hash"]) == 64
        assert "payload_hash" in ev and len(ev["payload_hash"]) == 64
    print(
        f"  [VERIFIED] Audit export JSON verified: {export_data['event_count']} events, "
        f"top_level_digest={export_data['top_level_digest'][:12]}... (integrity check passed)"
    )

    # Scroll to align the signed approvals card with 40px top padding
    page.locator('h3:has-text("Signed approvals")').first.evaluate(
        "el => window.scrollTo(0, el.getBoundingClientRect().top + window.scrollY - 40)"
    )
    page.wait_for_timeout(600)

    print("Verifying Screenshot 3 bounding boxes:")
    assert_element_in_captured_region(
        page.locator('h3:has-text("Signed approvals")').first, viewport_w, viewport_h, "Signed Approvals Heading"
    )
    assert_element_in_captured_region(
        page.locator('text=/Dr. Elena Rostova/i').first, viewport_w, viewport_h, "QA Lead Signature"
    )
    assert_element_in_captured_region(
        page.locator('text=/Sarah Jenkins/i').first, viewport_w, viewport_h, "Customer Ops Signature"
    )
    assert_element_in_captured_region(
        page.locator('text=/Signed phone attestation attached/i').first, viewport_w, viewport_h, "Signed Phone Attestation Box"
    )
    assert_element_in_captured_region(
        page.locator('h3:has-text("Consignee outbox")').first, viewport_w, viewport_h, "Consignee Outbox Heading"
    )
    assert_element_in_captured_region(
        page.locator('text=/6 of 6 confirmed/i').first, viewport_w, viewport_h, "6 of 6 Confirmed Indicator"
    )
    assert_element_in_captured_region(
        page.locator('text=/Phone attestation/i').first, viewport_w, viewport_h, "ACK-006 Phone Attestation Verified"
    )

    path3 = IMAGES_DIR / "03_audit_trail_and_export.png"
    page.screenshot(path=str(path3), full_page=False)
    print(f"  [SAVED] {path3.name} ({path3.stat().st_size} bytes)")

    context.close()


# ---------------------------------------------------------------------------
# Main Runner with Ephemeral Database and Process Lifecycle
# ---------------------------------------------------------------------------


def main() -> None:
    temp_dir = tempfile.mkdtemp(prefix="lot_zero_test_")
    temp_db = Path(temp_dir) / "test_isolated.db"
    port = find_free_port()
    base_url = f"http://127.0.0.1:{port}"

    env = os.environ.copy()
    env["LOT_ZERO_EVALUATION_MODE"] = "true"
    env["GOOGLE_GENAI_USE_VERTEXAI"] = "false"
    env.pop("GEMINI_API_KEY", None)
    env["LOT_ZERO_DB_PATH"] = str(temp_db)
    env["LOT_ZERO_DATABASE_PATH"] = str(temp_db)

    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "lot_zero.app:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--app-dir",
        str(ROOT / "apps" / "api" / "src"),
    ]

    print(f"Launching isolated test server on {base_url} (db: {temp_db})...")
    server = subprocess.Popen(cmd, env=env)

    try:
        if not wait_for_server(base_url):
            raise RuntimeError(f"Server on {base_url} failed to start within timeout.")
        print("Server is healthy.")

        with sync_playwright() as p:
            browser = p.chromium.launch(channel="msedge", headless=True)

            # 1. Run all 4 independent browser regression test scenarios
            run_scenario_a_normal_storage(browser, base_url)
            run_scenario_b_storage_getter_throws(browser, base_url)
            run_scenario_c_storage_methods_throw(browser, base_url)
            run_scenario_d_config_failure_and_retry(browser, base_url)

            # 2. Recapture meaningful screenshots with bounding-box proofs
            capture_screenshots_and_verify_export(browser, base_url)

            browser.close()

        print("\nAll browser regression checks and screenshot captures passed successfully!")

    finally:
        print("Shutting down test server...")
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
        # Clean up temporary database directory
        shutil.rmtree(temp_dir, ignore_errors=True)
        print("Cleaned up temporary database.")


if __name__ == "__main__":
    main()
