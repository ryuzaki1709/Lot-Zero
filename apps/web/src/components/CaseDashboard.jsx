import React, { useState, useEffect } from 'react';
import { RefreshCw, CheckCircle2, AlertCircle, Clock, ShieldCheck } from 'lucide-react';

const API_BASE = '';
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
    <div
      className="card-panel"
      style={{
        margin: '0 24px 16px',
        padding: '16px 20px',
      }}
    >
      {/* Header & Controls */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '14px', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <div className="section-label" style={{ marginBottom: '2px' }}>Read-Model Projections</div>
          <h2 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)' }}>
            Tenant incident query layer
          </h2>
          <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>
            Materialized read-models queried directly from append-only SQLite event stream
          </p>
        </div>

        <button
          className="btn btn-secondary"
          onClick={() => fetchCases(activeTab)}
          title="Re-query projections from SQLite event stream"
        >
          <RefreshCw size={12} />
          Refresh
        </button>
      </div>

      {/* Filter Tabs */}
      <div
        style={{
          display: 'flex',
          gap: '6px',
          borderBottom: '1px solid var(--border-subtle)',
          paddingBottom: '10px',
          marginBottom: '14px',
          overflowX: 'auto',
        }}
      >
        {[
          { id: 'all', label: 'All Incidents' },
          { id: 'open_holds', label: 'Open Holds' },
          { id: 'pending_qa', label: 'Pending QA Approval' },
          { id: 'blocked_by_rejections', label: 'Blocked by Refusals' },
        ].map((tab) => {
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`btn ${isActive ? 'btn-secondary' : 'btn-ghost'}`}
              style={{
                fontSize: '12px',
                padding: '4px 10px',
                borderColor: isActive ? 'var(--accent-primary)' : 'transparent',
                color: isActive ? 'var(--text-primary)' : 'var(--text-secondary)',
              }}
            >
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Case Projections Grid */}
      {loading ? (
        <div style={{ padding: '20px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '13px' }}>
          Loading projected summaries...
        </div>
      ) : error ? (
        <div style={{ padding: '10px 14px', background: 'var(--status-danger-subtle)', border: '1px solid rgba(239, 68, 68, 0.2)', borderRadius: 'var(--radius-md)', color: 'var(--status-danger-text)', fontSize: '12px', marginBottom: '14px' }}>
          {error}
        </div>
      ) : cases.length === 0 ? (
        <div style={{ padding: '20px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '13px' }}>
          No cases match filter <strong>{activeTab}</strong>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: '10px', marginBottom: '16px' }}>
          {cases.map((c) => {
            const isSelected = c.case_id === currentCaseId;
            return (
              <div
                key={c.case_id}
                onClick={() => onSelectCase && onSelectCase(c.case_id)}
                className="card-panel card-panel-interactive"
                style={{
                  padding: '12px',
                  borderColor: isSelected ? 'var(--accent-primary)' : 'var(--border-subtle)',
                  background: isSelected ? 'var(--bg-surface-elevated)' : 'var(--bg-surface-subtle)',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                  <span className="mono-val" style={{ fontWeight: 600, color: 'var(--text-primary)', fontSize: '13px' }}>
                    {c.case_id}
                  </span>
                  <span className="status-tag mono-val" style={{ fontSize: '11px', padding: '1px 6px' }}>
                    v{c.case_version} · {c.phase}
                  </span>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '12px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: 'var(--text-muted)' }}>Active Holds</span>
                    <span className="mono-val" style={{ color: c.has_open_holds ? 'var(--status-warning-text)' : 'var(--text-secondary)' }}>
                      {c.has_open_holds ? `${c.open_hold_quantity} units` : 'None'}
                    </span>
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ color: 'var(--text-muted)' }}>QA Review</span>
                    <span style={{ display: 'flex', alignItems: 'center', gap: '4px', color: c.has_pending_qa ? 'var(--status-danger-text)' : 'var(--status-success-text)' }}>
                      <span className={`status-dot ${c.has_pending_qa ? 'status-dot-danger' : 'status-dot-success'}`} />
                      {c.has_pending_qa ? `Pending (${c.pending_qa_type || 'review'})` : 'Satisfied'}
                    </span>
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ color: 'var(--text-muted)' }}>Consignee Refusals</span>
                    <span className="mono-val" style={{ color: c.has_rejected_acks ? 'var(--status-danger-text)' : 'var(--text-secondary)' }}>
                      {c.has_rejected_acks ? `${c.rejected_ack_count} active rejection` : '0'}
                    </span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Dual-Signature Release Rail & Case Lifecycle Milestone */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', borderTop: '1px solid var(--border-subtle)', paddingTop: '14px' }}>
        {/* Dual-Signature Rail */}
        <div style={{ background: 'var(--bg-surface-subtle)', padding: '12px 14px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
          <div className="section-label" style={{ marginBottom: '8px' }}>
            Dual-Signature Release Rail
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '12px' }}>
              <div
                style={{
                  width: '18px',
                  height: '18px',
                  borderRadius: '50%',
                  background: qaReleaseApp ? 'var(--status-success-subtle)' : 'var(--bg-surface-elevated)',
                  border: `1px solid ${qaReleaseApp ? 'var(--status-success)' : 'var(--border-subtle)'}`,
                  color: qaReleaseApp ? 'var(--status-success-text)' : 'var(--text-muted)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '10px',
                  fontWeight: 600,
                }}
              >
                1
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ color: 'var(--text-primary)', fontWeight: 500 }}>Step 1: QA Biological Clearance</div>
                <div style={{ color: 'var(--text-muted)', fontSize: '11px' }}>
                  {qaReleaseApp ? `Signed by ${qaReleaseApp.approver_id}` : 'Awaiting negative re-test citation & signature'}
                </div>
              </div>
              <span className={`status-tag ${qaReleaseApp ? 'status-tag-success' : ''}`} style={{ fontSize: '10px' }}>
                {qaReleaseApp ? 'Verified' : 'Pending'}
              </span>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '12px' }}>
              <div
                style={{
                  width: '18px',
                  height: '18px',
                  borderRadius: '50%',
                  background: hasReleaseAction ? 'var(--status-success-subtle)' : 'var(--bg-surface-elevated)',
                  border: `1px solid ${hasReleaseAction ? 'var(--status-success)' : 'var(--border-subtle)'}`,
                  color: hasReleaseAction ? 'var(--status-success-text)' : 'var(--text-muted)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '10px',
                  fontWeight: 600,
                }}
              >
                2
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ color: 'var(--text-primary)', fontWeight: 500 }}>Step 2: Closure Authority Release</div>
                <div style={{ color: 'var(--text-muted)', fontSize: '11px' }}>
                  {hasReleaseAction ? 'Inventory released & hold archived' : (qaReleaseApp ? 'Ready for Closure Authority signature' : 'Requires Step 1 biological clearance first')}
                </div>
              </div>
              <span className={`status-tag ${hasReleaseAction ? 'status-tag-success' : ''}`} style={{ fontSize: '10px' }}>
                {hasReleaseAction ? 'Released' : (qaReleaseApp ? 'Ready' : 'Locked')}
              </span>
            </div>
          </div>
        </div>

        {/* Milestone Progression */}
        <div style={{ background: 'var(--bg-surface-subtle)', padding: '12px 14px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
          <div className="section-label" style={{ marginBottom: '8px' }}>
            Case Lifecycle Milestone
          </div>
          <div style={{ fontSize: '12px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-muted)' }}>Current Phase:</span>
              <span className="mono-val" style={{ color: 'var(--accent-primary)', fontWeight: 600 }}>
                {activePhase || 'signal_received'}
              </span>
            </div>
            <div style={{ color: 'var(--text-muted)', fontSize: '11px', lineHeight: '1.4' }}>
              Phase sequence: signal_received → scope_review → provisional_containment → action_review → ack_monitoring → effectiveness_check → closed
            </div>
            <div style={{ color: 'var(--text-muted)', fontSize: '10px', marginTop: '2px' }}>
              All state transitions are appended to SQLite event log with optimistic concurrency.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
