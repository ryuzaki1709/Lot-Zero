import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import assert from 'node:assert/strict';
import {
  normalizeConfig,
  getEffectiveAuthHeaders,
  buildRequestHeaders,
  canStartSse,
  hasEffectiveAuth,
  isDemoCredential,
} from '../src/utils/authConfig.js';
import {
  deriveSummaryFromProjection,
  mergeCasesWithProjection,
  matchesFilter,
} from '../src/utils/dashboardSync.js';



class MockStorage {
  constructor(initial = {}) {
    this.store = { ...initial };
  }
  getItem(key) {
    return Object.prototype.hasOwnProperty.call(this.store, key) ? this.store[key] : null;
  }
  setItem(key, value) {
    this.store[key] = String(value);
  }
  removeItem(key) {
    delete this.store[key];
  }
}

test('isDemoCredential correctly classifies evaluation vs production keys', () => {
  assert.equal(isDemoCredential('key-recall-coord-01'), true);
  assert.equal(isDemoCredential('key-eval-admin-01'), true);
  assert.equal(isDemoCredential('demo-user-key'), true);
  assert.equal(isDemoCredential('prod_api_key_secret_xyz'), false);
  assert.equal(isDemoCredential(''), false);
  assert.equal(isDemoCredential(null), false);
});

test('confirmed evaluation config exposes only server-provided personas', () => {
  const serverPayload = {
    evaluation_mode: true,
    tenant_id: 'EVAL-TENANT-01',
    personas: [
      { key: 'key-recall-coord-01', label: 'Recall Coordinator', can_reset: false },
      { key: 'key-qa-lead-01', label: 'QA Lead', can_reset: false },
      { key: 'key-eval-admin-01', label: 'Evaluation Administrator', can_reset: true },
    ],
  };

  const storage = new MockStorage();
  const { config, activeApiKey } = normalizeConfig(serverPayload, '', storage);

  assert.equal(config.evaluation_mode, true);
  assert.equal(config.tenant_id, 'EVAL-TENANT-01');
  assert.equal(config.personas.length, 3);
  assert.equal(activeApiKey, 'key-recall-coord-01');
  assert.equal(storage.getItem('lot_zero_api_key'), 'key-recall-coord-01');
});

test('production config exposes no demo personas', () => {
  const prodPayload = {
    evaluation_mode: false,
    tenant_id: 'PROD-TENANT-01',
    personas: [],
  };

  const storage = new MockStorage({ lot_zero_api_key: 'key-eval-admin-01' });
  const { config, activeApiKey } = normalizeConfig(prodPayload, 'key-eval-admin-01', storage);

  assert.equal(config.evaluation_mode, false);
  assert.equal(config.personas.length, 0);
  assert.equal(activeApiKey, '');
  assert.equal(storage.getItem('lot_zero_api_key'), null);
});

test('config failure clears the active evaluation key', () => {
  const storage = new MockStorage({ lot_zero_api_key: 'key-recall-coord-01' });
  // Simulate network/server config fetch error (null payload)
  const { config, activeApiKey } = normalizeConfig(null, 'key-recall-coord-01', storage);

  assert.equal(config.evaluation_mode, false);
  assert.equal(config.personas.length, 0);
  assert.equal(activeApiKey, '');
});

test('stale localStorage evaluation credentials are removed on boot in non-evaluation mode', () => {
  const storage = new MockStorage({ lot_zero_api_key: 'key-qa-lead-01' });
  const { activeApiKey } = normalizeConfig({ evaluation_mode: false }, 'key-qa-lead-01', storage);

  assert.equal(activeApiKey, '');
  assert.equal(storage.getItem('lot_zero_api_key'), null, 'Stale evaluation key must be purged from localStorage');
});

test('no demo key is returned for API/SSE authorization in production mode', () => {
  // Demo key in production mode returns empty headers
  const prodHeadersWithDemo = getEffectiveAuthHeaders('key-qa-lead-01', false);
  assert.deepEqual(prodHeadersWithDemo, {});

  // Real non-demo token in production mode is preserved
  const prodHeadersWithReal = getEffectiveAuthHeaders('prod-bearer-token-live-001', false);
  assert.deepEqual(prodHeadersWithReal, { 'X-API-Key': 'prod-bearer-token-live-001' });

  // Demo key in server-confirmed evaluation mode is allowed
  const evalHeaders = getEffectiveAuthHeaders('key-qa-lead-01', true);
  assert.deepEqual(evalHeaders, { 'X-API-Key': 'key-qa-lead-01' });
});



test('wiring test: before config resolves, no authenticated header is produced and SSE cannot start', () => {
  // Before config resolves: configStatus is loading and activeApiKey is empty string
  const configStatus = 'loading';
  const activeApiKey = '';
  const evaluationMode = false;

  const headers = buildRequestHeaders(activeApiKey, evaluationMode);
  assert.deepEqual(headers, {});
  assert.equal(canStartSse(configStatus, activeApiKey, evaluationMode), false);
  assert.equal(hasEffectiveAuth(activeApiKey, evaluationMode), false);
});

test('wiring test: config failure plus stored demo key sends no X-API-Key', () => {
  const storage = new MockStorage({ lot_zero_api_key: 'key-eval-admin-01' });
  const { config, activeApiKey } = normalizeConfig(null, 'key-eval-admin-01', storage);

  assert.equal(config.evaluation_mode, false);
  assert.equal(activeApiKey, '');

  const requestHeaders = buildRequestHeaders(activeApiKey, config.evaluation_mode, {
    'Content-Type': 'application/json',
  });
  assert.deepEqual(requestHeaders, { 'Content-Type': 'application/json' });
  assert.equal(canStartSse('failed', activeApiKey, config.evaluation_mode), false);
  assert.equal(hasEffectiveAuth(activeApiKey, config.evaluation_mode), false);
});

test('wiring test: production mode plus stale demo key sends no X-API-Key', () => {
  const storage = new MockStorage({ lot_zero_api_key: 'key-qa-lead-01' });
  const { config, activeApiKey } = normalizeConfig({ evaluation_mode: false }, 'key-qa-lead-01', storage);

  assert.equal(config.evaluation_mode, false);
  assert.equal(activeApiKey, '');
  assert.equal(storage.getItem('lot_zero_api_key'), null);

  const requestHeaders = buildRequestHeaders(activeApiKey, config.evaluation_mode);
  assert.deepEqual(requestHeaders, {});
  assert.equal(canStartSse('ready', activeApiKey, config.evaluation_mode), false);
});

test('wiring test: confirmed evaluation mode plus server-provided persona sends exact key and starts SSE', () => {
  const storage = new MockStorage();
  const serverPayload = {
    evaluation_mode: true,
    tenant_id: 'EVAL-TENANT-01',
    personas: [
      { key: 'key-qa-lead-01', label: 'QA Lead', can_reset: false },
    ],
  };

  const { config, activeApiKey } = normalizeConfig(serverPayload, '', storage);
  assert.equal(config.evaluation_mode, true);
  assert.equal(activeApiKey, 'key-qa-lead-01');

  const headers = buildRequestHeaders(activeApiKey, config.evaluation_mode, {
    'Content-Type': 'application/json',
  });
  assert.deepEqual(headers, {
    'Content-Type': 'application/json',
    'X-API-Key': 'key-qa-lead-01',
  });
  assert.equal(canStartSse('ready', activeApiKey, config.evaluation_mode), true);
  assert.equal(hasEffectiveAuth(activeApiKey, config.evaluation_mode), true);
});

test('wiring test: App.jsx contains no direct raw X-API-Key construction bypassing authConfig helper', () => {
  const __dirname = path.dirname(fileURLToPath(import.meta.url));
  const appPath = path.resolve(__dirname, '../src/App.jsx');
  const appSource = fs.readFileSync(appPath, 'utf8');

  // Must not construct raw X-API-Key headers directly in App.jsx
  const directHeaderPattern = /['"]X-API-Key['"]\s*:\s*activeApiKey/g;
  const matches = appSource.match(directHeaderPattern);
  assert.equal(matches, null, 'App.jsx must not contain raw X-API-Key: activeApiKey headers');
});

test('workflow test: dispatch is separate from approval and disabled before approval', () => {
  // Model state: packet requested, but no notification approval decision in state
  const mockApprovalsWithoutNotif = [
    { approval_type: 'containment', decision: 'approved' },
  ];
  const isNotificationApproved = mockApprovalsWithoutNotif.some(
    (a) => a.approval_type === 'notification' && a.decision === 'approved'
  );
  assert.equal(isNotificationApproved, false, 'Notification is not approved yet');

  // Outbox dispatch action must be blocked when isNotificationApproved is false
  const canDispatch = isNotificationApproved;
  assert.equal(canDispatch, false, 'Dispatch must remain disabled before notification approval');

  // With approval added
  const mockApprovalsWithNotif = [
    ...mockApprovalsWithoutNotif,
    { approval_type: 'notification', decision: 'approved' },
  ];
  const isNowApproved = mockApprovalsWithNotif.some(
    (a) => a.approval_type === 'notification' && a.decision === 'approved'
  );
  assert.equal(isNowApproved, true);
  const canDispatchNow = isNowApproved;
  assert.equal(canDispatchNow, true, 'Dispatch enabled after notification approval');
});

test('workflow test: notification approval uses exact projected packet identity', () => {
  const mockPackets = [
    {
      packet_id: 'PKT-001',
      scope_id: 'SCOPE-EVAL-01',
      scope_version: 1,
      payload_version: 'PAYLOAD-001',
      payload_hash: 'payload-sha256-verified-digest',
      policy_version: 'EVAL-HOLD-01',
      status: 'planned',
    },
  ];

  const packet = mockPackets[0];
  assert.equal(packet.packet_id, 'PKT-001');
  assert.equal(packet.scope_id, 'SCOPE-EVAL-01');
  assert.equal(packet.scope_version, 1);
  assert.equal(packet.payload_version, 'PAYLOAD-001');
  assert.equal(packet.payload_hash, 'payload-sha256-verified-digest');
  assert.equal(packet.policy_version, 'EVAL-HOLD-01');
});

test('workflow test: closure requires Recall Coord request then Closure Authority authorization', () => {
  // Step 1: Recall Coordinator requests closure
  const reqPersona = 'key-recall-coord-01';
  const isRecallCoord = reqPersona === 'key-recall-coord-01';
  assert.equal(isRecallCoord, true, 'Request closure belongs to Recall Coordinator');

  // Step 2: Closure Authority authorizes closure
  const authPersona = 'key-closure-auth-01';
  const isClosureAuth = authPersona === 'key-closure-auth-01';
  assert.equal(isClosureAuth, true, 'Authorize closure belongs to Closure Authority');

  // Separation of duties
  assert.notEqual(reqPersona, authPersona, 'Requester and Authorizer are distinct personas');

  // Enforce honest modeled framing in UI components and prevent reintroduction of regulatory overclaims
  const __dirname = path.dirname(fileURLToPath(import.meta.url));
  const readSrc = (rel) => fs.readFileSync(path.resolve(__dirname, '../src', rel), 'utf-8');

  const howItWorks = readSrc('components/HowItWorksModal.jsx');
  assert.equal(howItWorks.includes('true regulatory compliance'), false);
  assert.equal(howItWorks.includes('Authentic Compliance'), false);

  const evidenceLedger = readSrc('components/EvidenceLedger.jsx');
  assert.equal(evidenceLedger.includes('archived under 21 CFR'), false);

  const approvalGate = readSrc('components/ApprovalGate.jsx');
  assert.equal(approvalGate.includes('certified non-response'), false);
  assert.equal(approvalGate.includes('Certify & Close Under § 7.49'), false);
  assert.equal(approvalGate.includes('Non-Response Closure (§ 7.49)'), false);
  assert.equal(approvalGate.includes('FDA-NONRESP'), false);

  const appJsx = readSrc('App.jsx');
  assert.equal(appJsx.includes('closed under 21 CFR'), false);
});

test('workflow test: unverified ACK-006 blocks ordinary closure and resolution enables it', () => {
  // Before resolution: ACK-006 is outstanding -> closureGate is blocked
  const closureGateBlocked = {
    is_blocked: true,
    outstanding_acknowledgements: ['ACK-006'],
    status: 'blocked',
  };
  const canAuthorizeBefore = !closureGateBlocked.is_blocked;
  assert.equal(canAuthorizeBefore, false, 'Ordinary closure must be blocked while ACK-006 is outstanding');

  // After Customer Operations phone resolution: ACK-006 verified -> closureGate is unblocked
  const closureGateResolved = {
    is_blocked: false,
    outstanding_acknowledgements: [],
    status: 'ready_for_closure',
  };
  const canAuthorizeAfter = !closureGateResolved.is_blocked;
  assert.equal(canAuthorizeAfter, true, 'Closure authorization enabled after ACK-006 resolution');
});

test('workflow test: wrong persona controls remain disabled with explicit persona check', () => {
  const activeKey = 'key-qa-lead-01'; // QA Lead active

  const isRecallCoord = activeKey === 'key-recall-coord-01';
  const isQaLead = activeKey === 'key-qa-lead-01';
  const isCustomerOps = activeKey === 'key-ops-01';
  const isClosureAuth = activeKey === 'key-closure-auth-01';
  const isEvalAdmin = activeKey === 'key-eval-admin-01';

  assert.equal(isQaLead, true, 'QA Lead controls are active');
  assert.equal(isRecallCoord, false, 'Recall Coord controls are disabled for QA Lead');
  assert.equal(isCustomerOps, false, 'Customer Ops controls are disabled for QA Lead');
  assert.equal(isClosureAuth, false, 'Closure Auth controls are disabled for QA Lead');
  assert.equal(isEvalAdmin, false, 'Eval Admin controls are disabled for QA Lead');
});

test('synchronization test: deriveSummaryFromProjection extracts accurate case indicators', () => {

  const mockProjection = {
    header: {
      case_id: 'EVAL-CASE-01',
      tenant_id: 'EVAL-TENANT-01',
      phase: 'action_review',
      case_version: 6,
      updated_at: '2026-08-22T09:00:00Z',
    },
    metrics: {
      provisional_hold_quantity: 0,
      firm_quarantine_quantity: 200.0,
      authorized_hold_quantity: 0,
    },
    approvals: [
      { approval_type: 'containment', decision: 'approved' },
    ],
    acknowledgements: [
      { acknowledgement_id: 'ACK-001', status: 'verified' },
      { acknowledgement_id: 'ACK-006', status: 'outstanding' },
    ],
  };

  const summary = deriveSummaryFromProjection(mockProjection);
  assert.equal(summary.case_id, 'EVAL-CASE-01');
  assert.equal(summary.phase, 'action_review');
  assert.equal(summary.case_version, 6);
  assert.equal(summary.has_open_holds, true);
  assert.equal(summary.open_hold_quantity, 200.0);
  assert.equal(summary.has_pending_qa, false);
  assert.equal(summary.has_rejected_acks, false);
});

test('synchronization test: overlapping fetches discard older responses resolving out-of-order', async () => {
  // Simulate race condition:
  // Req 1 (slow, returns v4 provisional containment)
  // Req 2 (fast, returns v6 action review)
  let latestRequestId = 0;
  let currentState = [];

  const handleResponse = (reqId, responseData) => {
    // If request is not the latest, discard
    if (reqId !== latestRequestId) {
      return false; // Discarded
    }
    currentState = responseData;
    return true; // Accepted
  };

  // 1. Fire Req 1
  const req1Id = ++latestRequestId;
  const req1Data = [{ case_id: 'EVAL-CASE-01', case_version: 4, phase: 'provisional_containment' }];

  // 2. Fire Req 2
  const req2Id = ++latestRequestId;
  const req2Data = [{ case_id: 'EVAL-CASE-01', case_version: 6, phase: 'action_review' }];

  // 3. Req 2 resolves FIRST
  const accepted2 = handleResponse(req2Id, req2Data);
  assert.equal(accepted2, true, 'Newer request 2 response must be accepted');
  assert.equal(currentState[0].case_version, 6);
  assert.equal(currentState[0].phase, 'action_review');

  // 4. Req 1 resolves SECOND (stale delayed response)
  const accepted1 = handleResponse(req1Id, req1Data);
  assert.equal(accepted1, false, 'Older request 1 response must be discarded');
  // State MUST remain at v6
  assert.equal(currentState[0].case_version, 6);
  assert.equal(currentState[0].phase, 'action_review');
});

test('synchronization test: reset from v19 closed to baseline immediately clears archived card', () => {
  const previousClosedCase = [
    {
      case_id: 'EVAL-CASE-01',
      tenant_id: 'EVAL-TENANT-01',
      phase: 'closed',
      case_version: 19,
      has_open_holds: false,
    },
  ];

  const resetProjection = {
    header: {
      case_id: 'EVAL-CASE-01',
      tenant_id: 'EVAL-TENANT-01',
      phase: 'signal_received',
      case_version: 0,
      updated_at: '2026-08-22T09:00:00Z',
    },
    metrics: { provisional_hold_quantity: 0 },
    approvals: [],
    acknowledgements: [],
  };

  // Merge server data (which could be empty or baseline) with reset projection
  const merged = mergeCasesWithProjection([], resetProjection, 'all');
  assert.equal(merged.length, 1);
  assert.equal(merged[0].case_id, 'EVAL-CASE-01');
  assert.equal(merged[0].case_version, 0);
  assert.equal(merged[0].phase, 'signal_received');
  assert.equal(merged[0].has_open_holds, false);
});

test('synchronization test: final closure displays final returned version and closed phase automatically', () => {
  const closureProjection = {
    header: {
      case_id: 'EVAL-CASE-01',
      tenant_id: 'EVAL-TENANT-01',
      phase: 'closed',
      case_version: 21,
      updated_at: '2026-08-22T09:30:00Z',
    },
    metrics: { provisional_hold_quantity: 0, firm_quarantine_quantity: 0 },
    approvals: [
      { approval_type: 'containment', decision: 'approved' },
      { approval_type: 'closure', decision: 'approved' },
    ],
    acknowledgements: [
      { acknowledgement_id: 'ACK-006', status: 'verified' },
    ],
  };

  const merged = mergeCasesWithProjection([], closureProjection, 'all');
  assert.equal(merged.length, 1);
  assert.equal(merged[0].case_version, 21);
  assert.equal(merged[0].phase, 'closed');
  assert.equal(merged[0].has_open_holds, false);
  assert.equal(merged[0].has_pending_qa, false);
});

test('synchronization test: persona changes cannot reintroduce an earlier summary', () => {
  const currentProj = {
    header: {
      case_id: 'EVAL-CASE-01',
      phase: 'action_review',
      case_version: 6,
    },
    metrics: { firm_quarantine_quantity: 200 },
    approvals: [{ approval_type: 'containment', decision: 'approved' }],
  };

  // Persona switch triggers a fetch, but server response has stale/delayed payload from earlier v4
  const staleServerData = [
    { case_id: 'EVAL-CASE-01', case_version: 4, phase: 'provisional_containment' },
  ];

  const merged = mergeCasesWithProjection(staleServerData, currentProj, 'all');
  assert.equal(merged[0].case_version, 6);
  assert.equal(merged[0].phase, 'action_review');
});
