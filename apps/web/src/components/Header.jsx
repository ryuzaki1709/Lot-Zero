import React from 'react';
import { ShieldAlert, RefreshCw, Cpu, BookOpen, Radio, Sparkles, FileCode, CheckCircle2 } from 'lucide-react';

export function Header({
  projection,
  onSimulateSignal,
  onReset,
  onOpenHowItWorks,
  loading,
  sseConnected,
}) {
  const modelName = projection?.runtime?.model?.value || 'gemini-2.5-flash (Google GenAI)';
  const docHash = projection?.header?.source_doc_hash || 'd8f3a9e14417b89...';
  const docVersion = projection?.header?.source_doc_version || 'v1.0 (Signed Apex Labs Report)';
  const isQaApproved = projection?.approvals?.some(a => a.decision === 'approved');

  return (
    <header style={{ position: 'relative', zIndex: 10, marginBottom: '20px' }}>
      {/* Top Operational Status Bar (Facility & Transport State) */}
      <div
        style={{
          background: 'rgba(15, 23, 42, 0.9)',
          borderBottom: '1px solid var(--border-subtle)',
          padding: '6px 20px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          fontSize: '0.78rem',
          color: 'var(--text-secondary)',
          fontFamily: 'var(--font-mono)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span style={{ color: 'var(--accent-amber)', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span className="pulse-dot" style={{ backgroundColor: 'var(--accent-amber)' }} />
            Evaluation tenant · synthetic records · no real outreach
          </span>
          <span style={{ color: 'rgba(255,255,255,0.2)' }}>|</span>
          <span>Facility: <strong>EVAL-TENANT-01 (Minneapolis)</strong></span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          <span>Case: <strong>{projection?.header?.case_id || 'EVAL-CASE-01'}</strong></span>
          <span style={{ color: 'rgba(255,255,255,0.2)' }}>|</span>
          <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
            <Radio size={12} color={sseConnected ? 'var(--accent-emerald)' : 'var(--accent-rose)'} />
            {sseConnected ? 'SSE Live (127.0.0.1:8000)' : 'Transport Disconnected'}
          </span>
        </div>
      </div>

      {/* Main Navigation Cockpit */}
      <div
        className="glass-panel"
        style={{
          margin: '14px 20px 0',
          padding: '14px 22px',
          display: 'flex',
          flexWrap: 'wrap',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: '14px',
        }}
      >
        {/* Title & Brand */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          <div
            style={{
              width: '40px',
              height: '40px',
              borderRadius: '10px',
              background: 'linear-gradient(135deg, rgba(6,182,212,0.2) 0%, rgba(2,132,199,0.3) 100%)',
              border: '1px solid var(--border-active)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <ShieldAlert size={22} color="var(--accent-cyan)" />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <h1 style={{ fontSize: '1.35rem', fontWeight: 800, letterSpacing: '-0.02em' }}>
                LOT ZERO
              </h1>
              <span className="badge badge-cyan">FDA/USDA RECALL WAR ROOM</span>
              {/* Separate AI Provenance Badge */}
              <span className="badge badge-emerald" title={`Model: ${modelName}`}>
                <Cpu size={12} /> {modelName}
              </span>
            </div>
            <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '2px', display: 'flex', gap: '12px' }}>
              <span>Doc Ver: <strong>{docVersion}</strong></span>
              <span>SHA-256: <code style={{ color: 'var(--accent-cyan)' }}>{docHash.substring(0, 14)}...</code></span>
              <span>Policy: <strong style={{ color: isQaApproved ? 'var(--accent-emerald)' : 'var(--accent-amber)' }}>{isQaApproved ? 'AUTH-HOLD-01 (Firm Quarantine)' : 'EVAL-HOLD-01 (30m Soft Hold)'}</strong></span>
            </div>
          </div>
        </div>

        {/* Action Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
          {/* 
            SECURITY NOTICE: This in-UI API key switcher is strictly for local evaluation and demonstration harnesses.
            In production deployments, keys/tokens must NEVER be embedded in client bundles; real authentication (OAuth2 / OIDC / Session)
            must be used instead.
          */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', background: 'rgba(30, 41, 59, 0.7)', padding: '4px 8px', borderRadius: '6px', border: '1px solid rgba(148, 163, 184, 0.2)' }}>
            <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Caller Key:</span>
            <select
              value={activeApiKey || 'key-recall-coord-01'}
              onChange={(e) => onApiKeyChange && onApiKeyChange(e.target.value)}
              style={{
                background: '#0f172a',
                color: '#f8fafc',
                border: '1px solid rgba(148, 163, 184, 0.3)',
                borderRadius: '4px',
                padding: '4px 8px',
                fontSize: '0.78rem',
                outline: 'none',
                cursor: 'pointer',
              }}
            >
              <option value="key-recall-coord-01">Recall Coordinator (key-recall-coord-01)</option>
              <option value="key-qa-lead-01">QA Lead (key-qa-lead-01)</option>
              <option value="key-ops-01">Customer Operations (key-ops-01)</option>
              <option value="key-closure-auth-01">Closure Authority (key-closure-auth-01)</option>
              <option value="key-agent-svc-01">Agent Service (key-agent-svc-01)</option>
            </select>
          </div>

          <button
            className="btn-kinetic btn-primary"
            onClick={onSimulateSignal}
            disabled={loading}
            title="Simulate incoming Salmonella lab safety signal and trigger Gemini agent"
          >
            <Sparkles size={15} />
            Simulate Signal
          </button>

          <button
            className="btn-kinetic btn-secondary"
            onClick={onExportAudit}
            disabled={loading}
            title="Export tamper-evident cryptographically chained audit bundle"
            style={{ border: '1px solid rgba(59, 130, 246, 0.5)' }}
          >
            <FileCode size={14} color="#60a5fa" />
            Audit Export (.json)
          </button>

          <button
            className="btn-kinetic btn-secondary"
            onClick={onReset}
            disabled={loading}
            title="Reset to clean baseline"
          >
            <RefreshCw size={14} />
            Reset
          </button>

          <button
            className="btn-kinetic btn-secondary"
            onClick={onOpenHowItWorks}
            title="Open Judge Architecture & Evaluation Guide"
          >
            <BookOpen size={14} />
            Guide
          </button>
        </div>
      </div>
    </header>
  );
}
