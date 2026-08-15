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
import './styles/antigravity.css';

const API_BASE = 'http://127.0.0.1:8000';

// SECURITY NOTE: These evaluation keys match the server's default demo environment in auth.py.
// For production deployments, keys must NOT be present in client-side code; use server-issued sessions / OAuth.
const KEY_COORD = 'key-recall-coord-01';
const KEY_QA = 'key-qa-lead-01';
const KEY_OPS = 'key-ops-01';
const KEY_CLOSURE = 'key-closure-auth-01';

export function App() {
  const [currentCaseId, setCurrentCaseId] = useState('EVAL-CASE-01');
  const [activeApiKey, setActiveApiKey] = useState(
    localStorage.getItem('lot_zero_api_key') || 'key-recall-coord-01'
  );
  const [projection, setProjection] = useState(null);
  const [loading, setLoading] = useState(false);
  const [sseConnected, setSseConnected] = useState(false);
  const [isHowItWorksOpen, setIsHowItWorksOpen] = useState(false);
  const [attestationData, setAttestationData] = useState(null);

  const handleApiKeyChange = (key) => {
    setActiveApiKey(key);
    localStorage.setItem('lot_zero_api_key', key);
  };

  const handleExportAudit = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/cases/${currentCaseId}/audit-export`, {
        headers: { 'X-API-Key': activeApiKey },
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
      } else {
        const err = await res.json();
        alert(`Audit export failed (${res.status}): ${err.detail || res.statusText}`);
      }
    } catch (err) {
      alert(`Audit export network error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  // Fetch initial projection and subscribe to SSE
  useEffect(() => {
    let eventSource;

    const fetchInitial = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/incidents/${currentCaseId}`, {
          headers: { 'X-API-Key': activeApiKey },
        });
        if (res.ok) {
          const data = await res.json();
          setProjection(data);
        }
      } catch (err) {
        console.warn('API connecting... using initial baseline');
      }
    };

    fetchInitial();

    try {
      eventSource = new EventSource(`${API_BASE}/api/incidents/${currentCaseId}/events`);
      eventSource.onopen = () => {
        setSseConnected(true);
      };
      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          setProjection(data);
        } catch (e) {
          console.error('Error parsing SSE payload', e);
        }
      };
      eventSource.onerror = () => {
        setSseConnected(false);
      };
    } catch (e) {
      console.warn('EventSource initialization error', e);
    }

    return () => {
      if (eventSource) eventSource.close();
    };
  }, [currentCaseId, activeApiKey]);

  const handleSimulateSignal = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/evaluation/simulate-signal`, {
        method: 'POST',
        headers: { 'X-API-Key': activeApiKey },
      });
      if (res.ok) {
        const data = await res.json();
        if (data.projection) setProjection(data.projection);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleApproveContainment = async (rationale) => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/evaluation/approve-containment`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': activeApiKey === 'key-qa-lead-01' ? activeApiKey : KEY_QA,
        },
        body: JSON.stringify({ role: 'qa', rationale }),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.projection) setProjection(data.projection);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleDispatchOutbox = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/evaluation/dispatch-outbox`, {
        method: 'POST',
        headers: { 'X-API-Key': activeApiKey === 'key-ops-01' ? activeApiKey : KEY_OPS },
      });
      if (res.ok) {
        const data = await res.json();
        if (data.projection) setProjection(data.projection);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleResolveAck = async (payload) => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/evaluation/resolve-ack`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': activeApiKey === 'key-ops-01' ? activeApiKey : KEY_OPS,
        },
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        const data = await res.json();
        setAttestationData(data);
        if (data.projection) setProjection(data.projection);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleRequestClosure = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/evaluation/request-closure`, {
        method: 'POST',
        headers: { 'X-API-Key': activeApiKey === 'key-closure-auth-01' ? activeApiKey : KEY_CLOSURE },
      });
      if (res.ok) {
        const data = await res.json();
        if (data.projection) setProjection(data.projection);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleReleaseHold = async (payload) => {
    setLoading(true);
    try {
      // Step 1: QA Lead biological clearance signature
      const res1 = await fetch(`${API_BASE}/api/evaluation/release-hold/step`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': KEY_QA,
        },
        body: JSON.stringify({
          retest_doc_id: payload.retest_doc_id,
          retest_doc_hash: payload.retest_doc_hash,
          role: 'qa',
          principal_id: 'QA-LEAD-01',
          rationale: payload.qa_rationale,
        }),
      });
      if (!res1.ok) {
        const err = await res1.json();
        console.error('QA Step Error:', err);
        return;
      }

      // Step 2: Closure Authority operational un-hold signature
      const res2 = await fetch(`${API_BASE}/api/evaluation/release-hold/step`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': KEY_CLOSURE,
        },
        body: JSON.stringify({
          retest_doc_id: payload.retest_doc_id,
          retest_doc_hash: payload.retest_doc_hash,
          role: 'closure_authority',
          principal_id: 'CLOSURE-AUTH-01',
          rationale: payload.coordinator_rationale,
        }),
      });
      if (res2.ok) {
        const data = await res2.json();
        if (data.projection) setProjection(data.projection);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleCloseWithNonResponse = async (payload) => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/evaluation/close-with-non-response`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': KEY_CLOSURE,
        },
        body: JSON.stringify({
          principal_id: 'CLOSURE-AUTH-01',
          attempt_count: 3,
          regulatory_filing_id: payload?.regulatory_filing_id || 'FDA-DISTRICT-ESCALATION-2026-08-01',
          good_faith_notes: payload?.good_faith_notes || 'Documented 3 verified contact attempts to RECIPIENT-006 (phone, certified email, courier delivery). Consignee non-responsive. Referral filed with FDA District Office under 21 CFR § 7.49.',
        }),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.projection) setProjection(data.projection);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleReset = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/evaluation/reset`, {
        method: 'POST',
        headers: { 'X-API-Key': activeApiKey },
      });
      if (res.ok) {
        const data = await res.json();
        setAttestationData(null);
        if (data.projection) setProjection(data.projection);
      }
    } catch (err) {
      console.error(err);
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
  const isQaApproved = approvals?.some((a) => a.decision === 'approved' && a.approval_type === 'containment');

  return (
    <div style={{ position: 'relative', minHeight: '100vh', paddingBottom: '40px' }}>
      <KineticBackground />

      <Header
        projection={projection}
        onSimulateSignal={handleSimulateSignal}
        onReset={handleReset}
        onOpenHowItWorks={() => setIsHowItWorksOpen(true)}
        onExportAudit={handleExportAudit}
        activeApiKey={activeApiKey}
        onApiKeyChange={handleApiKeyChange}
        loading={loading}
        sseConnected={sseConnected}
      />

      <div style={{ margin: '0 20px 16px' }}>
        <CaseDashboard
          currentCaseId={currentCaseId}
          onSelectCase={(id) => setCurrentCaseId(id)}
          activePhase={phase}
          approvals={approvals}
          containmentActions={projection?.containment_actions}
          apiKey={activeApiKey}
        />
      </div>

      <StageProgress phase={phase} metrics={metrics} closureGate={closureGate} />

      {/* Main Operational 3-Column Cockpit */}
      <main
        style={{
          position: 'relative',
          zIndex: 10,
          margin: '0 20px',
          display: 'grid',
          gridTemplateColumns: 'minmax(280px, 1fr) minmax(380px, 1.4fr) minmax(280px, 1fr)',
          gap: '18px',
          alignItems: 'start',
        }}
      >
        {/* Column 1: Signal Ingestion & Citations */}
        <section style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
          <SignalViewer signal={signal} scopes={projection?.scopes} modelName={modelName} />
        </section>

        {/* Column 2: Bidirectional DAG & Dual Human Decision Gate */}
        <section style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
          <GenealogyGraph
            genealogy={genealogy}
            metrics={metrics}
            phase={phase}
            isQaApproved={isQaApproved}
          />
          <ApprovalGate
            phase={phase}
            onApproveContainment={handleApproveContainment}
            onDispatchOutbox={handleDispatchOutbox}
            onResolveAck={handleResolveAck}
            onRequestClosure={handleRequestClosure}
            onReleaseHold={handleReleaseHold}
            onCloseWithNonResponse={handleCloseWithNonResponse}
            loading={loading}
            approvals={approvals}
            closureGate={closureGate}
          />
        </section>

        {/* Column 3: Evidence Ledger, Signed Audit Signatures & Consignee Acks */}
        <section style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
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
