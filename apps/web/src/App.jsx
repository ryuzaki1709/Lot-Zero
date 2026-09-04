import React, { useState, useEffect } from 'react';
import { KineticBackground } from './components/KineticBackground';
import { Header } from './components/Header';
import { CaseDashboard } from './components/CaseDashboard';
import { StageProgress } from './components/StageProgress';
import { SignalViewer } from './components/SignalViewer';
import { GenealogyGraph } from './components/GenealogyGraph';
import { ApprovalGate } from './components/ApprovalGate';
import { EvidenceLedger } from './components/EvidenceLedger';
import { HowItWorksModal } from './components/HowItWorksModal';
import { normalizeConfig, buildRequestHeaders, canStartSse } from './utils/authConfig';
import './styles/antigravity.css';
import './styles/responsive.css';

const API_BASE = '';

export function App() {
  const [currentCaseId, setCurrentCaseId] = useState('EVAL-CASE-01');
  const [configStatus, setConfigStatus] = useState('loading'); // 'loading' | 'ready' | 'failed'
  const [activeApiKey, setActiveApiKey] = useState('');
  const [appConfig, setAppConfig] = useState({ evaluation_mode: false, tenant_id: '', personas: [] });
  const [projection, setProjection] = useState(null);
  const [loading, setLoading] = useState(false);
  const [sseConnected, setSseConnected] = useState(false);
  const [isHowItWorksOpen, setIsHowItWorksOpen] = useState(false);
  const [attestationData, setAttestationData] = useState(null);
  const [feedback, setFeedback] = useState(null); // { type: 'error' | 'success', message: string }

  // Load server-side runtime configuration and evaluation personas (fail-closed)
  useEffect(() => {
    fetch(`${API_BASE}/api/config`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        const storedKey = localStorage.getItem('lot_zero_api_key') || '';
        const { config, activeApiKey: resolvedKey } = normalizeConfig(data, storedKey, localStorage);
        setAppConfig(config);
        setActiveApiKey(resolvedKey);
        setConfigStatus(data ? 'ready' : 'failed');
      })
      .catch(() => {
        const storedKey = localStorage.getItem('lot_zero_api_key') || '';
        const { config, activeApiKey: resolvedKey } = normalizeConfig(null, storedKey, localStorage);
        setAppConfig(config);
        setActiveApiKey(resolvedKey);
        setConfigStatus('failed');
      });
  }, []);

  const handleApiKeyChange = (key) => {
    setActiveApiKey(key);
    if (key) {
      localStorage.setItem('lot_zero_api_key', key);
    } else {
      localStorage.removeItem('lot_zero_api_key');
    }
    setFeedback(null);
  };



  const handleApiError = async (res, defaultAction = 'Action') => {
    let detail = res.statusText;
    try {
      const err = await res.json();
      detail = err.detail || detail;
    } catch (_) {}
    setFeedback({
      type: 'error',
      message: `Refused (${res.status}): ${detail}`,
    });
  };

  const handleExportAudit = async () => {
    setLoading(true);
    setFeedback(null);
    try {
      const res = await fetch(`${API_BASE}/api/cases/${currentCaseId}/audit-export`, {
        headers: buildRequestHeaders(activeApiKey, appConfig.evaluation_mode),
      });
      if (res.ok) {
        const data = await res.json();
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `audit-export-${currentCaseId}-${Date.now()}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        setFeedback({ type: 'success', message: 'Audit export bundle downloaded successfully.' });
      } else {
        await handleApiError(res, 'Audit export');
      }
    } catch (err) {
      setFeedback({ type: 'error', message: `Network error: ${err.message}` });
    } finally {
      setLoading(false);
    }
  };

  // Fetch initial projection and subscribe to SSE only after config resolves and auth is valid
  useEffect(() => {
    if (configStatus !== 'ready') {
      return;
    }

    let eventSource = null;
    let isCancelled = false;
    let reconnectTimeout = null;

    const authHeaders = buildRequestHeaders(activeApiKey, appConfig.evaluation_mode);

    const fetchInitial = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/incidents/${currentCaseId}`, {
          headers: authHeaders,
        });
        if (res.ok) {
          const data = await res.json();
          if (!isCancelled) setProjection(data);
        } else {
          if (!isCancelled) await handleApiError(res, 'Fetch incident');
        }
      } catch (err) {
        console.warn('API connecting... using initial baseline');
      }
    };

    fetchInitial();

    const connectSSE = async () => {
      if (!canStartSse(configStatus, activeApiKey, appConfig.evaluation_mode)) {
        if (!isCancelled) setSseConnected(false);
        return;
      }

      try {
        const tokenRes = await fetch(`${API_BASE}/api/sse-token`, {
          method: 'POST',
          headers: authHeaders,
        });
        if (!tokenRes.ok) {
          if (!isCancelled) setSseConnected(false);
          return;
        }
        const tokenData = await tokenRes.json();
        if (isCancelled) return;

        eventSource = new EventSource(
          `${API_BASE}/api/incidents/${currentCaseId}/events?token=${encodeURIComponent(tokenData.token)}`
        );
        eventSource.onopen = () => {
          if (!isCancelled) setSseConnected(true);
        };
        eventSource.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            if (!isCancelled) setProjection(data);
          } catch (e) {
            console.error('Error parsing SSE payload', e);
          }
        };
        eventSource.onerror = () => {
          if (!isCancelled) setSseConnected(false);
          if (eventSource) {
            eventSource.close();
            eventSource = null;
          }
          if (!isCancelled) {
            reconnectTimeout = setTimeout(connectSSE, 3000);
          }
        };
      } catch (e) {
        if (!isCancelled) setSseConnected(false);
      }
    };

    connectSSE();

    return () => {
      isCancelled = true;
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
      if (eventSource) eventSource.close();
    };
  }, [currentCaseId, activeApiKey, configStatus, appConfig.evaluation_mode]);

  const handleSimulateSignal = async () => {
    setLoading(true);
    setFeedback(null);
    try {
      const res = await fetch(`${API_BASE}/api/evaluation/simulate-signal`, {
        method: 'POST',
        headers: buildRequestHeaders(activeApiKey, appConfig.evaluation_mode),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.projection) setProjection(data.projection);
        setFeedback({ type: 'success', message: 'Safety signal simulated and parsed via Gemini.' });
      } else {
        await handleApiError(res, 'Simulate signal');
      }
    } catch (err) {
      setFeedback({ type: 'error', message: `Network error: ${err.message}` });
    } finally {
      setLoading(false);
    }
  };

  const handleApproveContainment = async (rationale) => {
    setLoading(true);
    setFeedback(null);
    try {
      const res = await fetch(`${API_BASE}/api/evaluation/approve-containment`, {
        method: 'POST',
        headers: buildRequestHeaders(activeApiKey, appConfig.evaluation_mode, {
          'Content-Type': 'application/json',
        }),
        body: JSON.stringify({ rationale }),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.projection) setProjection(data.projection);
        setFeedback({ type: 'success', message: 'Firm quarantine approved by QA Lead.' });
      } else {
        await handleApiError(res, 'Approve containment');
      }
    } catch (err) {
      setFeedback({ type: 'error', message: `Network error: ${err.message}` });
    } finally {
      setLoading(false);
    }
  };

  const handleRequestNotification = async () => {
    setLoading(true);
    setFeedback(null);
    try {
      const res = await fetch(`${API_BASE}/api/evaluation/request-notification`, {
        method: 'POST',
        headers: buildRequestHeaders(activeApiKey, appConfig.evaluation_mode),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.projection) setProjection(data.projection);
        setFeedback({ type: 'success', message: 'Notification packet PKT-001 drafted and requested by Recall Coordinator.' });
      } else {
        await handleApiError(res, 'Request notification');
      }
    } catch (err) {
      setFeedback({ type: 'error', message: `Network error: ${err.message}` });
    } finally {
      setLoading(false);
    }
  };

  const handleApproveNotification = async (payload) => {
    setLoading(true);
    setFeedback(null);
    try {
      const res = await fetch(`${API_BASE}/api/evaluation/approve-notification`, {
        method: 'POST',
        headers: buildRequestHeaders(activeApiKey, appConfig.evaluation_mode, {
          'Content-Type': 'application/json',
        }),
        body: JSON.stringify({
          packet_id: payload.packet_id,
          scope_id: payload.scope_id,
          scope_version: payload.scope_version,
          payload_version: payload.payload_version,
          payload_hash: payload.payload_hash,
          policy_version: payload.policy_version,
          rationale: payload.rationale,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.projection) setProjection(data.projection);
        setFeedback({ type: 'success', message: 'Recall notification packet payload approved by Customer Operations.' });
      } else {
        await handleApiError(res, 'Approve notification');
      }
    } catch (err) {
      setFeedback({ type: 'error', message: `Network error: ${err.message}` });
    } finally {
      setLoading(false);
    }
  };

  const handleDispatchOutbox = async () => {
    setLoading(true);
    setFeedback(null);
    try {
      const res = await fetch(`${API_BASE}/api/evaluation/dispatch-outbox`, {
        method: 'POST',
        headers: buildRequestHeaders(activeApiKey, appConfig.evaluation_mode),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.projection) setProjection(data.projection);
        setFeedback({ type: 'success', message: 'Recall notification packet dispatched to consignees.' });
      } else {
        await handleApiError(res, 'Dispatch outbox');
      }
    } catch (err) {
      setFeedback({ type: 'error', message: `Network error: ${err.message}` });
    } finally {
      setLoading(false);
    }
  };

  const handleResolveAck = async (payload) => {
    setLoading(true);
    setFeedback(null);
    try {
      const res = await fetch(`${API_BASE}/api/evaluation/resolve-ack`, {
        method: 'POST',
        headers: buildRequestHeaders(activeApiKey, appConfig.evaluation_mode, {
          'Content-Type': 'application/json',
        }),
        body: JSON.stringify({
          caller_id: payload.caller_id,
          recipient_contact: payload.recipient_contact,
          recipient_phone: payload.recipient_phone,
          call_timestamp: payload.call_timestamp,
          attestation_notes: payload.attestation_notes,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setAttestationData(data);
        if (data.projection) setProjection(data.projection);
        setFeedback({ type: 'success', message: 'Phone attestation signed and recorded into audit ledger.' });
      } else {
        await handleApiError(res, 'Resolve acknowledgement');
      }
    } catch (err) {
      setFeedback({ type: 'error', message: `Network error: ${err.message}` });
    } finally {
      setLoading(false);
    }
  };

  const handleRequestClosure = async () => {
    setLoading(true);
    setFeedback(null);
    try {
      const res = await fetch(`${API_BASE}/api/evaluation/request-closure`, {
        method: 'POST',
        headers: buildRequestHeaders(activeApiKey, appConfig.evaluation_mode),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.projection) setProjection(data.projection);
        setFeedback({ type: 'success', message: `Closure review requested (${data.request_id || 'REQ-CLOSE'}). Pending Closure Authority authorization.` });
      } else {
        await handleApiError(res, 'Request closure');
      }
    } catch (err) {
      setFeedback({ type: 'error', message: `Network error: ${err.message}` });
    } finally {
      setLoading(false);
    }
  };

  const handleAuthorizeClosure = async (requestId) => {
    setLoading(true);
    setFeedback(null);
    try {
      const res = await fetch(`${API_BASE}/api/evaluation/authorize-closure`, {
        method: 'POST',
        headers: buildRequestHeaders(activeApiKey, appConfig.evaluation_mode, {
          'Content-Type': 'application/json',
        }),
        body: JSON.stringify({
          request_id: requestId || undefined,
          rationale: 'Verified all consignee acknowledgements and containment complete.',
        }),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.projection) setProjection(data.projection);
        if (data.blocked) {
          const blockingStr =
            data.outstanding_acknowledgements && data.outstanding_acknowledgements.length > 0
              ? data.outstanding_acknowledgements.join(', ')
              : 'outstanding consignee acknowledgement';
          setFeedback({
            type: 'error',
            message: `Refused: Closure blocked — unverified consignee acknowledgements remain (${blockingStr}).`,
          });
        } else {
          setFeedback({ type: 'success', message: 'Incident case closed successfully.' });
        }
      } else {
        await handleApiError(res, 'Authorize closure');
      }
    } catch (err) {
      setFeedback({ type: 'error', message: `Network error: ${err.message}` });
    } finally {
      setLoading(false);
    }
  };


  // Perform exactly ONE release step per invocation, signed by the active role
  const handleReleaseHold = async (payload) => {
    setLoading(true);
    setFeedback(null);
    try {
      const res = await fetch(`${API_BASE}/api/evaluation/release-hold/step`, {
        method: 'POST',
        headers: buildRequestHeaders(activeApiKey, appConfig.evaluation_mode, {
          'Content-Type': 'application/json',
        }),
        body: JSON.stringify({
          retest_doc_id: payload.retest_doc_id,
          retest_doc_hash: payload.retest_doc_hash,
          rationale: payload.rationale,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.projection) setProjection(data.projection);
        setFeedback({
          type: 'success',
          message:
            data.role === 'qa'
              ? 'Step 1 complete: QA Lead biological clearance signed. Switch role to Closure Authority for Step 2.'
              : 'Step 2 complete: Operational inventory release authorized and hold archived.',
        });
      } else {
        await handleApiError(res, 'Release step');
      }
    } catch (err) {
      setFeedback({ type: 'error', message: `Network error: ${err.message}` });
    } finally {
      setLoading(false);
    }
  };

  const handleCloseWithNonResponse = async (payload) => {
    setLoading(true);
    setFeedback(null);
    try {
      const res = await fetch(`${API_BASE}/api/evaluation/close-with-non-response`, {
        method: 'POST',
        headers: buildRequestHeaders(activeApiKey, appConfig.evaluation_mode, {
          'Content-Type': 'application/json',
        }),
        body: JSON.stringify({
          attempt_count: payload.attempt_count,
          regulatory_filing_id: payload.regulatory_filing_id,
          good_faith_notes: payload.good_faith_notes,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.projection) setProjection(data.projection);
        setFeedback({
          type: 'success',
          message: 'Incident closed with synthetic non-response documentation and modeled referral note (not a legal or regulatory certification).',
        });
      } else {
        await handleApiError(res, 'Non-response closure');
      }
    } catch (err) {
      setFeedback({ type: 'error', message: `Network error: ${err.message}` });
    } finally {
      setLoading(false);
    }
  };

  const handleReset = async () => {
    setLoading(true);
    setFeedback(null);
    try {
      const res = await fetch(`${API_BASE}/api/evaluation/reset`, {
        method: 'POST',
        headers: buildRequestHeaders(activeApiKey, appConfig.evaluation_mode),
      });
      if (res.ok) {
        const data = await res.json();
        setAttestationData(null);
        if (data.projection) setProjection(data.projection);
        setFeedback({ type: 'success', message: 'Incident baseline reset cleanly.' });
      } else {
        await handleApiError(res, 'Reset baseline');
      }
    } catch (err) {
      setFeedback({ type: 'error', message: `Network error: ${err.message}` });
    } finally {
      setLoading(false);
    }
  };

  const phase = projection?.header?.phase || 'signal_received';
  const signal = projection?.signal;
  const genealogy = projection?.genealogy;
  const metrics = projection?.metrics;
  const closureGate = projection?.closure_gate;
  const acks = projection?.acknowledgements;
  const approvals = projection?.approvals;
  const ledgerCount = projection?.ledger_count;
  const modelName = projection?.runtime?.model?.value;
  const isQaApproved = approvals?.some(
    (a) => a.decision === 'approved' && a.approval_type === 'containment'
  );
  const isActionDisabled = loading || configStatus !== 'ready';

  return (
    <div className="app-shell">
      <KineticBackground />

      <Header
        projection={projection}
        onSimulateSignal={handleSimulateSignal}
        onReset={handleReset}
        onOpenHowItWorks={() => setIsHowItWorksOpen(true)}
        onExportAudit={handleExportAudit}
        activeApiKey={activeApiKey}
        onApiKeyChange={handleApiKeyChange}
        loading={isActionDisabled}
        sseConnected={sseConnected}
        personas={appConfig.personas}
        evaluationMode={appConfig.evaluation_mode}
      />


      <div className="stepper-container">
        <StageProgress phase={phase} metrics={metrics} closureGate={closureGate} />
      </div>

      {/* Group 4a: Context selection (CaseDashboard) directly under StageProgress */}
      <div className="case-dashboard-container">
        <CaseDashboard
          currentCaseId={currentCaseId}
          onSelectCase={(id) => setCurrentCaseId(id)}
          activePhase={phase}
          apiKey={activeApiKey}
          evaluationMode={appConfig.evaluation_mode}
          refreshTrigger={projection?.header?.case_version}
          currentProjection={projection}
        />
      </div>



      {/* Main Operational Responsive Cockpit */}
      <main className="cockpit-grid">
        {/* Global Denial/Error Surface (Group 1c) */}
        {feedback && (
          <div
            style={{
              gridColumn: '1 / -1',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              padding: '10px 14px',
              borderRadius: 'var(--radius-md)',
              background:
                feedback.type === 'error'
                  ? 'var(--status-danger-subtle)'
                  : 'var(--status-success-subtle)',
              border: `1px solid ${
                feedback.type === 'error'
                  ? 'rgba(239, 68, 68, 0.3)'
                  : 'rgba(34, 197, 94, 0.3)'
              }`,
              color:
                feedback.type === 'error'
                  ? 'var(--status-danger-text)'
                  : 'var(--status-success-text)',
              fontSize: '13px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span
                className={`status-dot ${
                  feedback.type === 'error' ? 'status-dot-danger' : 'status-dot-success'
                }`}
              />
              <span style={{ fontWeight: 500 }}>{feedback.message}</span>
            </div>
            <button
              className="btn btn-ghost"
              style={{ padding: '2px 6px', fontSize: '11px', color: 'inherit' }}
              onClick={() => setFeedback(null)}
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Column 1: Signal Ingestion & Citations */}
        <section className="cockpit-column">
          <SignalViewer signal={signal} scopes={projection?.scopes} modelName={modelName} />
        </section>

        {/* Column 2: Bidirectional DAG & Decision Gates */}
        <section className="cockpit-column">
          <GenealogyGraph
            genealogy={genealogy}
            metrics={metrics}
            phase={phase}
            isQaApproved={isQaApproved}
          />
          <ApprovalGate
            phase={phase}
            onApproveContainment={handleApproveContainment}
            onRequestNotification={handleRequestNotification}
            onApproveNotification={handleApproveNotification}
            onDispatchOutbox={handleDispatchOutbox}
            onResolveAck={handleResolveAck}
            onRequestClosure={handleRequestClosure}
            onAuthorizeClosure={handleAuthorizeClosure}
            onReleaseHold={handleReleaseHold}
            onCloseWithNonResponse={handleCloseWithNonResponse}
            loading={isActionDisabled}
            approvals={approvals}
            closureGate={closureGate}
            containmentActions={projection?.containment_actions}
            packets={projection?.packets}
            closureRequests={projection?.closure_requests}
            activeApiKey={activeApiKey}
            evaluationMode={appConfig.evaluation_mode}
          />

        </section>

        {/* Column 3: Evidence Ledger, Signed Audit Signatures & Consignee Acks */}
        <section className="cockpit-column">
          <EvidenceLedger
            acknowledgements={acks}
            closureGate={closureGate}
            ledgerCount={ledgerCount}
            approvals={approvals}
            phase={phase}
            attestationData={attestationData}
          />
        </section>
      </main>

      <HowItWorksModal isOpen={isHowItWorksOpen} onClose={() => setIsHowItWorksOpen(false)} />
    </div>
  );
}
