import os
import time
import json
import urllib.request
from playwright.sync_api import sync_playwright

target_url = 'http://127.0.0.1:8000'
screenshots_dir = 'C:/Users/sujan reddy/Documents/john/lot-zero/screenshots'
os.makedirs(screenshots_dir, exist_ok=True)

def reset_baseline():
    req = urllib.request.Request(
        f'{target_url}/api/evaluation/reset',
        data=b'{}',
        headers={'Content-Type': 'application/json', 'X-API-Key': 'key-recall-coord-01'},
        method='POST'
    )
    with urllib.request.urlopen(req) as r:
        assert r.status == 200

# Problem 2 detector code exact implementation
raw_detector_script = '''() => {
    const vw = document.documentElement.clientWidth;
    const bad = [...document.querySelectorAll('*')]
      .map(el => { const r = el.getBoundingClientRect();
                   return { el, left: r.left, right: r.right }; })
      .filter(o => o.right > vw + 1 || o.left < -1)
      .map(o => ({
        tag: o.el.tagName,
        cls: o.el.className && o.el.className.toString().slice(0, 60),
        left: Math.round(o.left),
        right: Math.round(o.right),
        overflowBy: Math.round(Math.max(o.right - vw, -o.left))
      }));
    return bad;
}'''

viewports = [
    ('320', 320, 568),
    ('360', 360, 640),
    ('390', 390, 844),
    ('430', 430, 932),
    ('768', 768, 1024),
    ('1024', 1024, 768),
    ('1440', 1440, 900),
    ('844x390', 844, 390),
]

audit_results = []

with sync_playwright() as p:
    browser = p.chromium.launch(channel='msedge', headless=True)
    
    for name, w, h in viewports:
        reset_baseline()
        page = browser.new_page(viewport={'width': w, 'height': h})
        page.goto(target_url, wait_until='networkidle')
        
        # Test 1: Empty state (Guarded)
        bad_empty_g = page.evaluate(raw_detector_script)
        
        # Test 2: Empty state (UNGUARDED)
        page.evaluate('''() => {
            document.documentElement.style.overflowX = 'visible';
            document.body.style.overflowX = 'visible';
        }''')
        bad_empty_u = page.evaluate(raw_detector_script)
        
        # Reset guard for interaction
        page.evaluate('''() => {
            document.documentElement.style.overflowX = 'hidden';
            document.body.style.overflowX = 'hidden';
        }''')
        
        # 1. Simulate signal
        page.locator('button:has-text("Simulate signal")').click()
        page.wait_for_timeout(1000)
        
        # 2. QA Lead approves firm quarantine
        page.locator('select').select_option('key-qa-lead-01')
        page.wait_for_timeout(300)
        page.locator('button:has-text("Approve Firm Quarantine")').click()
        page.wait_for_timeout(600)
        
        # If 390, capture Modal 1 (Release Rail) and Modal 2 (Docs)
        if name == '390':
            print('Capturing Modal: Dual-Signature Release Rail (Gate 4)...')
            page.locator('button:has-text("Sign Step 1 (QA Lead)")').click()
            page.wait_for_timeout(400)
            page.screenshot(path=f'{screenshots_dir}/390_modal_release.png')
            page.keyboard.press('Escape')
            page.wait_for_timeout(400)
            
            print('Capturing Modal: Architecture Docs...')
            page.locator('button[title*="Architecture"]').click()
            page.wait_for_timeout(400)
            page.screenshot(path=f'{screenshots_dir}/390_modal_docs.png')
            page.keyboard.press('Escape')
            page.wait_for_timeout(400)
        
        # 3. Ops dispatches outbox
        page.locator('select').select_option('key-ops-01')
        page.wait_for_timeout(300)
        page.locator('button:has-text("Dispatch Recall Outbox (Ops)")').click()
        page.wait_for_timeout(600)
        
        # If 390, capture Modal 3 (Phone Attestation)
        if name == '390':
            print('Capturing Modal: Phone Attestation (Gate 3)...')
            page.locator('button:has-text("Verify Phone Attestation")').click()
            page.wait_for_timeout(400)
            page.screenshot(path=f'{screenshots_dir}/390_modal_phone.png')
            page.keyboard.press('Escape')
            page.wait_for_timeout(400)
        
        # 4. Switch to Closure Authority
        page.locator('select').select_option('key-closure-auth-01')
        page.wait_for_timeout(300)
        
        # If 390, capture Modal 4 (Non-Response Close § 7.49)
        if name == '390':
            print('Capturing Modal: Non-Response Close (§ 7.49) (Gate 5)...')
            page.locator('button:has-text("Non-Response Close")').click()
            page.wait_for_timeout(400)
            page.screenshot(path=f'{screenshots_dir}/390_modal_nonresponse.png')
            page.keyboard.press('Escape')
            page.wait_for_timeout(400)
        
        # Test 3: Populated state (Guarded)
        bad_pop_g = page.evaluate(raw_detector_script)
        
        # Test 4: Populated state (UNGUARDED)
        page.evaluate('''() => {
            document.documentElement.style.overflowX = 'visible';
            document.body.style.overflowX = 'visible';
        }''')
        bad_pop_u = page.evaluate(raw_detector_script)
        
        audit_results.append({
            'viewport': f'{name} ({w}x{h})',
            'empty_guarded': len(bad_empty_g),
            'empty_unguarded': len(bad_empty_u),
            'empty_offenders': bad_empty_u,
            'pop_guarded': len(bad_pop_g),
            'pop_unguarded': len(bad_pop_u),
            'pop_offenders': bad_pop_u,
        })
        
        page.close()
    browser.close()

reset_baseline()

print('\n=== AUDIT RESULTS TABLE ===')
for r in audit_results:
    print(f"{r['viewport']:22} | Empty Guarded: {r['empty_guarded']:2} | Empty Unguarded: {r['empty_unguarded']:2} | Pop Guarded: {r['pop_guarded']:2} | Pop Unguarded: {r['pop_unguarded']:2}")
    if r['empty_unguarded'] > 0:
        print('   Empty offenders:', r['empty_offenders'])
    if r['pop_unguarded'] > 0:
        print('   Pop offenders:  ', r['pop_offenders'])

# Verify modal screenshots existence and sizes
print('\n=== MODAL SCREENSHOTS ON DISK ===')
modal_files = [
    '390_modal_docs.png',
    '390_modal_release.png',
    '390_modal_phone.png',
    '390_modal_nonresponse.png',
]
for mf in modal_files:
    full_p = os.path.join(screenshots_dir, mf)
    exists = os.path.exists(full_p)
    sz = os.path.getsize(full_p) if exists else 0
    print(f'{mf:28}: exists={exists}, size={sz:7} bytes')
    assert exists and sz > 1000, f'Missing or empty screenshot: {mf}'
print('\nAll 4 modal screenshots 100% verified on disk!')
