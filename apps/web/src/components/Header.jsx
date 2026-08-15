import React from 'react';
import { RefreshCw, BookOpen, Download, Radio, Sparkles } from 'lucide-react';

export function Header({
  projection,
  onSimulateSignal,
  onReset,
  onOpenHowItWorks,
  loading,
  sseConnected,
  activeApiKey,
  onApiKeyChange,
  onExportAudit,
}) {
  const modelName = projection?.runtime?.model?.value || 'gemini-2.5-flash';
  const docHash = projection?.header?.source_doc_hash || 'd8f3a9e14417b89...';
  const docVersion = projection?.header?.source_doc_version || 'v1.0 (Signed Apex Labs Report)';
  const isQaApproved = projection?.approvals?.some((a) => a.decision === 'approved');

  return (
    <header style={{ marginBottom: '16px' }}>
      {/* Top Utility & Status Rail */}
      <div
        style={{
          background: 'var(--bg-app)',
          borderBottom: '1px solid var(--border-subtle)',
          padding: '6px 24px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          fontSize: '12px',
          color: 'var(--text-muted)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--text-secondary)' }}>
            <span className="status-dot status-dot-warning" />
            Evaluation tenant · synthetic records · no real outreach
          </span>
          <span style={{ color: 'var(--border-subtle)' }}>/</span>
          <span>Facility: <span style={{ color: 'var(--text-secondary)' }}>EVAL-TENANT-01 (Minneapolis)</span></span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <span>
            Case: <span className="mono-val" style={{ color: 'var(--text-primary)' }}>{projection?.header?.case_id || 'EVAL-CASE-01'}</span>
          </span>
          <span style={{ color: 'var(--border-subtle)' }}>/</span>
          <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span className={`status-dot ${sseConnected ? 'status-dot-success' : 'status-dot-danger'}`} />
            <span style={{ color: sseConnected ? 'var(--text-secondary)' : 'var(--status-danger-text)' }}>
              {sseConnected ? 'SSE Live' : 'Disconnected'}
            </span>
          </span>
        </div>
      </div>

      {/* Main App Navigation & Action Bar */}
      <div
        className="card-panel"
        style={{
          margin: '12px 24px 0',
          padding: '14px 18px',
          display: 'flex',
          flexWrap: 'wrap',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: '16px',
        }}
      >
        {/* Brand & Incident Scope Summary */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <h1 style={{ fontSize: '18px', fontWeight: 600, letterSpacing: '-0.02em', color: 'var(--text-primary)' }}>
                Lot Zero
              </h1>
              <span className="status-tag">Recall incident workspace</span>
              <span className="status-tag" style={{ color: 'var(--text-muted)' }}>
                <span className="status-dot status-dot-success" style={{ width: '5px', height: '5px' }} />
                {modelName}
              </span>
            </div>

            <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px', display: 'flex', gap: '14px', flexWrap: 'wrap' }}>
              <span>Doc: <span style={{ color: 'var(--text-secondary)' }}>{docVersion}</span></span>
              <span>
                SHA-256:{' '}
                <code className="mono-val" style={{ color: 'var(--text-secondary)' }}>
                  {docHash.substring(0, 12)}...
                </code>
              </span>
              <span>
                Policy:{' '}
                <span style={{ color: isQaApproved ? 'var(--status-success-text)' : 'var(--status-warning-text)' }}>
                  {isQaApproved ? 'AUTH-HOLD-01 (Firm Quarantine)' : 'EVAL-HOLD-01 (30m Soft Hold)'}
                </span>
              </span>
            </div>
          </div>
        </div>

        {/* Action Controls & Role Selector */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          {/* Caller Key Switcher */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginRight: '4px' }}>
            <span className="section-label" style={{ fontSize: '11px' }}>Role:</span>
            <select
              value={activeApiKey || 'key-recall-coord-01'}
              onChange={(e) => onApiKeyChange && onApiKeyChange(e.target.value)}
              style={{
                fontSize: '12px',
                padding: '5px 8px',
                minWidth: '180px',
              }}
            >
              <option value="key-recall-coord-01">Recall Coordinator</option>
              <option value="key-qa-lead-01">QA Lead</option>
              <option value="key-ops-01">Customer Operations</option>
              <option value="key-closure-auth-01">Closure Authority</option>
              <option value="key-agent-svc-01">Agent Service</option>
            </select>
          </div>

          {/* Secondary Actions */}
          <button
            className="btn btn-secondary"
            onClick={onExportAudit}
            disabled={loading}
            title="Download cryptographically hash-chained regulatory audit bundle"
          >
            <Download size={13} />
            Audit Export
          </button>

          <button
            className="btn btn-secondary"
            onClick={onOpenHowItWorks}
            title="Technical architecture & judge evaluation notes"
          >
            <BookOpen size={13} />
            Architecture
          </button>

          <button
            className="btn btn-ghost"
            onClick={onReset}
            disabled={loading}
            title="Reset incident state to clean baseline"
          >
            <RefreshCw size={13} />
            Reset
          </button>

          {/* Single Primary Action */}
          <button
            className="btn btn-primary"
            onClick={onSimulateSignal}
            disabled={loading}
            title="Ingest lab safety signal and trigger Gemini extraction"
          >
            <Sparkles size={14} />
            Simulate Signal
          </button>
        </div>
      </div>
    </header>
  );
}
