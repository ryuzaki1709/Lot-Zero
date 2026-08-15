import React, { useState, useEffect } from 'react';

const API_BASE = 'http://127.0.0.1:8000';
const DEFAULT_KEY = 'key-recall-coord-01';

export function CaseDashboard({
  currentCaseId,
  onSelectCase,
  activePhase,
  approvals = [],
  containmentActions = [],
  apiKey,
}) {
  const [activeTab, setActiveTab] = useState('all');
  const [cases, setCases] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchCases = async (filter) => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/projections/cases?filter=${filter}`, {
        headers: { 'X-API-Key': apiKey || DEFAULT_KEY },
      });
      if (res.ok) {
        const data = await res.json();
        setCases(data);
      } else {
        setError(`Failed to fetch cases: ${res.statusText}`);
      }
    } catch (err) {
      setError(err.message || 'Error connecting to projection service');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCases(activeTab);
  }, [activeTab, apiKey]);

  // Derive dual-signature release status from approvals and containment actions
  const qaReleaseApp = approvals.find((a) => a.approval_type === 'release' && a.approver_role === 'qa');
  const closureReleaseApp = approvals.find((a) => a.approval_type === 'release' && a.approver_role === 'closure_authority');
  const hasReleaseAction = containmentActions.some((a) => a.action_type === 'release_hold');

  return (
    <div className="case-dashboard-panel" style={{ marginBottom: '24px', background: 'rgba(15, 23, 42, 0.75)', border: '1px solid rgba(148, 163, 184, 0.2)', borderRadius: '12px', padding: '20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <h2 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 600, color: '#f8fafc' }}>Incident Query & Read Models</h2>
          <p style={{ margin: '4px 0 0', fontSize: '0.85rem', color: '#94a3b8' }}>
            Fast projections queried directly from append-only SQLite event stream (scoped to tenant)
          </p>
        </div>
        <button
          onClick={() => fetchCases(activeTab)}
          style={{ background: 'rgba(51, 65, 85, 0.8)', border: '1px solid rgba(148, 163, 184, 0.3)', color: '#f8fafc', padding: '6px 14px', borderRadius: '6px', cursor: 'pointer', fontSize: '0.85rem' }}
        >
          Refresh Query
        </button>
      </div>

      {/* Filter Tabs */}
      <div style={{ display: 'flex', gap: '8px', borderBottom: '1px solid rgba(148, 163, 184, 0.2)', paddingBottom: '12px', marginBottom: '16px', overflowX: 'auto' }}>
        {[
          { id: 'all', label: 'All Incidents' },
          { id: 'open_holds', label: 'Open Holds' },
          { id: 'pending_qa', label: 'Pending QA Approval' },
          { id: 'blocked_by_rejections', label: 'Blocked by Refusals' },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            style={{
              background: activeTab === tab.id ? '#3b82f6' : 'transparent',
              color: activeTab === tab.id ? '#ffffff' : '#94a3b8',
              border: activeTab === tab.id ? '1px solid #60a5fa' : '1px solid transparent',
              padding: '6px 14px',
              borderRadius: '6px',
              fontWeight: 500,
              fontSize: '0.85rem',
              cursor: 'pointer',
              transition: 'all 0.15s ease',
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Case Projection List */}
      {loading ? (
        <div style={{ padding: '16px', textAlign: 'center', color: '#94a3b8', fontSize: '0.9rem' }}>Loading projected summaries...</div>
      ) : error ? (
        <div style={{ padding: '12px', background: 'rgba(239, 68, 68, 0.15)', border: '1px solid rgba(239, 68, 68, 0.3)', borderRadius: '6px', color: '#fca5a5', fontSize: '0.85rem' }}>
          {error}
        </div>
      ) : cases.length === 0 ? (
        <div style={{ padding: '16px', textAlign: 'center', color: '#64748b', fontSize: '0.9rem' }}>
          No cases match filter <strong>{activeTab}</strong>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '12px', marginBottom: '20px' }}>
          {cases.map((c) => (
            <div
              key={c.case_id}
              onClick={() => onSelectCase && onSelectCase(c.case_id)}
              style={{
                background: c.case_id === currentCaseId ? 'rgba(59, 130, 246, 0.15)' : 'rgba(30, 41, 59, 0.6)',
                border: c.case_id === currentCaseId ? '1px solid #3b82f6' : '1px solid rgba(148, 163, 184, 0.2)',
                borderRadius: '8px',
                padding: '14px',
                cursor: 'pointer',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <span style={{ fontWeight: 600, color: '#f8fafc', fontSize: '0.95rem' }}>{c.case_id}</span>
                <span style={{ fontSize: '0.75rem', padding: '2px 8px', borderRadius: '12px', background: 'rgba(148, 163, 184, 0.15)', color: '#cbd5e1' }}>
                  v{c.case_version} · {c.phase}
                </span>
              </div>
              <div style={{ fontSize: '0.8rem', color: '#94a3b8', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <div>Holds: <strong style={{ color: c.has_open_holds ? '#fbbf24' : '#94a3b8' }}>{c.has_open_holds ? `${c.open_hold_quantity} units active` : 'None'}</strong></div>
                <div>QA Review: <strong style={{ color: c.has_pending_qa ? '#f87171' : '#34d399' }}>{c.has_pending_qa ? `Pending (${c.pending_qa_type || 'review'})` : 'Satisfied'}</strong></div>
                <div>Refusals: <strong style={{ color: c.has_rejected_acks ? '#ef4444' : '#94a3b8' }}>{c.has_rejected_acks ? `${c.rejected_ack_count} active rejection` : '0'}</strong></div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Dual-Signature Step Indicator & Simple Case Timeline */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginTop: '16px', borderTop: '1px solid rgba(148, 163, 184, 0.2)', paddingTop: '16px' }}>
        {/* Dual-Signature Release Rail */}
        <div style={{ background: 'rgba(15, 23, 42, 0.5)', padding: '14px', borderRadius: '8px', border: '1px solid rgba(148, 163, 184, 0.15)' }}>
          <h4 style={{ margin: '0 0 10px', fontSize: '0.9rem', color: '#e2e8f0', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Dual-Signature Release Rail
          </h4>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '0.85rem' }}>
              <div style={{ width: '22px', height: '22px', borderRadius: '50%', background: qaReleaseApp ? '#22c55e' : '#475569', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 'bold', fontSize: '0.75rem' }}>
                1
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ color: '#f8fafc', fontWeight: 500 }}>Step 1: QA Lead Biological Clearance</div>
                <div style={{ color: '#94a3b8', fontSize: '0.75rem' }}>{qaReleaseApp ? `Signed by ${qaReleaseApp.approver_id}` : 'Awaiting negative re-test citation & signature'}</div>
              </div>
              <span style={{ fontSize: '0.75rem', color: qaReleaseApp ? '#4ade80' : '#94a3b8' }}>{qaReleaseApp ? 'VERIFIED' : 'PENDING'}</span>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '0.85rem' }}>
              <div style={{ width: '22px', height: '22px', borderRadius: '50%', background: hasReleaseAction ? '#22c55e' : (qaReleaseApp ? '#3b82f6' : '#334155'), color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 'bold', fontSize: '0.75rem' }}>
                2
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ color: '#f8fafc', fontWeight: 500 }}>Step 2: Closure Authority Operational Release</div>
                <div style={{ color: '#94a3b8', fontSize: '0.75rem' }}>{hasReleaseAction ? 'Inventory released & hold archived' : (qaReleaseApp ? 'Ready for distinct Closure Authority signature' : 'Requires Step 1 biological clearance first')}</div>
              </div>
              <span style={{ fontSize: '0.75rem', color: hasReleaseAction ? '#4ade80' : (qaReleaseApp ? '#60a5fa' : '#64748b') }}>{hasReleaseAction ? 'RELEASED' : (qaReleaseApp ? 'READY' : 'LOCKED')}</span>
            </div>
          </div>
        </div>

        {/* Simple Case Timeline */}
        <div style={{ background: 'rgba(15, 23, 42, 0.5)', padding: '14px', borderRadius: '8px', border: '1px solid rgba(148, 163, 184, 0.15)' }}>
          <h4 style={{ margin: '0 0 10px', fontSize: '0.9rem', color: '#e2e8f0', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Case Lifecycle Milestone
          </h4>
          <div style={{ fontSize: '0.85rem', color: '#94a3b8', display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <div>Current Phase: <strong style={{ color: '#60a5fa' }}>{activePhase || 'signal_received'}</strong></div>
            <div>Phase Progression: <span style={{ color: '#e2e8f0' }}>signal_received → scope_review → provisional_containment → action_review → ack_monitoring → effectiveness_check → closed</span></div>
            <div style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '4px' }}>Every phase change is cryptographically witnessed via TransitionEvents in SQLite ledger.</div>
          </div>
        </div>
      </div>
    </div>
  );
}
