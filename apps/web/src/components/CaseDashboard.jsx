import React, { useState, useEffect } from 'react';
import { RefreshCw } from 'lucide-react';

const API_BASE = '';

export function CaseDashboard({
  currentCaseId,
  onSelectCase,
  activePhase,
  apiKey,
}) {
  const [activeTab, setActiveTab] = useState('all');
  const [cases, setCases] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchCases = async (filter) => {
    if (!apiKey) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/projections/cases?filter=${filter}`, {
        headers: { 'X-API-Key': apiKey },
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

  return (
    <section className="section" style={{ marginBottom: 0 }}>
      <div className="section-head">
        <div>
          <h2 className="section-title">Incidents</h2>
          <p className="section-desc">
            Read models materialized from the append-only event stream, scoped to this tenant.
          </p>
        </div>
        <button className="btn btn-ghost" onClick={() => fetchCases(activeTab)} title="Re-query projections">
          <RefreshCw size={14} />
          Refresh
        </button>
      </div>

      {/* Underline tabs */}
      <div className="tabs" style={{ marginBottom: '16px' }}>
        {[
          { id: 'all', label: 'All' },
          { id: 'open_holds', label: 'Open holds' },
          { id: 'pending_qa', label: 'Pending QA' },
          { id: 'blocked_by_rejections', label: 'Blocked by refusals' },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`tab ${activeTab === tab.id ? 'tab-active' : ''}`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Case cards */}
      {loading ? (
        <div style={{ padding: '24px 0', color: 'var(--text-muted)', fontSize: '13px' }}>
          Loading projections…
        </div>
      ) : error ? (
        <div style={{ padding: '12px 14px', border: '1px solid rgba(248, 113, 113, 0.25)', borderRadius: 'var(--radius-md)', color: 'var(--status-danger-text)', fontSize: '13px' }}>
          {error}
        </div>
      ) : cases.length === 0 ? (
        <div style={{ padding: '24px 0', color: 'var(--text-muted)', fontSize: '13px' }}>
          No cases match this filter.
        </div>
      ) : (
        <div className="grid-auto-sm">
          {cases.map((c) => {
            const isSelected = c.case_id === currentCaseId;
            return (
              <div
                key={c.case_id}
                onClick={() => onSelectCase && onSelectCase(c.case_id)}
                className="card-panel card-panel-interactive"
                style={{
                  padding: '16px',
                  borderColor: isSelected ? 'var(--accent-primary)' : 'var(--border-subtle)',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: '12px', gap: '8px' }}>
                  <span className="mono-val" style={{ fontWeight: 600, color: 'var(--text-primary)', fontSize: '13.5px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {c.case_id}
                  </span>
                  <span style={{ fontSize: '12px', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
                    v{c.case_version} · {String(c.phase || '').replace(/_/g, ' ')}
                  </span>
                </div>

                <dl>
                  <div className="def-row" style={{ padding: '5px 0' }}>
                    <dt>Active holds</dt>
                    <dd style={{ color: c.has_open_holds ? 'var(--status-warning-text)' : 'var(--text-secondary)' }}>
                      {c.has_open_holds ? `${c.open_hold_quantity} units` : 'None'}
                    </dd>
                  </div>
                  <div className="def-row" style={{ padding: '5px 0' }}>
                    <dt>QA review</dt>
                    <dd>
                      <span className="status-inline">
                        <span className={`status-dot ${c.has_pending_qa ? 'status-dot-warning' : 'status-dot-success'}`} />
                        {c.has_pending_qa ? `Pending · ${c.pending_qa_type || 'review'}` : 'Satisfied'}
                      </span>
                    </dd>
                  </div>
                  <div className="def-row" style={{ padding: '5px 0' }}>
                    <dt>Refusals</dt>
                    <dd style={{ color: c.has_rejected_acks ? 'var(--status-danger-text)' : 'var(--text-secondary)' }}>
                      {c.has_rejected_acks ? c.rejected_ack_count : '0'}
                    </dd>
                  </div>
                </dl>
              </div>
            );
          })}
        </div>
      )}

      {/* Lifecycle footer */}
      <div
        style={{
          marginTop: '16px',
          paddingTop: '14px',
          borderTop: '1px solid var(--border-subtle)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '12px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span className="section-label">Current Phase</span>
          <span style={{ color: 'var(--accent-primary)', fontWeight: 500, fontSize: '13px' }}>
            {String(activePhase || 'signal_received').replace(/_/g, ' ')}
          </span>
        </div>
        <p style={{ fontSize: '12px', color: 'var(--text-muted)', margin: 0 }}>
          Optimistic concurrency: state transitions enforced via append-only event stream.
        </p>
      </div>
    </section>
  );
}
