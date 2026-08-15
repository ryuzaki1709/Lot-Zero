import React, { useEffect, useRef, useState } from 'react';
import { RefreshCw, BookOpen, Download, Sparkles } from 'lucide-react';

/** Animates a number toward its target over ~600ms whenever it changes. */
function useCountUp(target) {
  const numTarget = typeof target === 'number' ? target : 0;
  const [display, setDisplay] = useState(numTarget);
  const fromRef = useRef(numTarget);

  useEffect(() => {
    const from = fromRef.current;
    if (from === numTarget) return;
    const start = performance.now();
    const duration = 600;
    let raf;
    const tick = (now) => {
      const p = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - p, 3);
      setDisplay(Math.round(from + (numTarget - from) * eased));
      if (p < 1) raf = requestAnimationFrame(tick);
      else fromRef.current = numTarget;
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [numTarget]);

  return typeof target === 'number' ? display : '-';
}

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
  const modelName = projection?.runtime?.model?.value || 'gemini-3.5-flash';
  const docHash = projection?.header?.source_doc_hash;
  const docVersion = projection?.header?.source_doc_version;
  const caseId = projection?.header?.case_id || 'EVAL-CASE-01';
  const isQaApproved = projection?.approvals?.some(
    (a) => a.decision === 'approved' && a.approval_type === 'containment'
  );
  const acks = projection?.acknowledgements || [];
  const confirmedAcks = acks.filter((a) => a.status === 'verified').length;
  const totalAcks = acks.length;

  const unitsHeld =
    projection?.metrics?.provisional_hold_quantity ??
    projection?.metrics?.affected_inventory_quantity ??
    (projection ? 0 : null);
  const falseHolds =
    projection?.metrics?.unaffected_hold_quantity ??
    projection?.metrics?.false_holds ??
    (projection ? 0 : null);
  const ledgerCount =
    projection?.ledger_count ??
    projection?.metrics?.ledger_entries_count ??
    (projection ? 0 : null);

  const hasSignal = Boolean(projection?.signal);

  const unitsDisplay = useCountUp(unitsHeld);
  const falseHoldsDisplay = useCountUp(falseHolds);
  const ledgerDisplay = useCountUp(ledgerCount);
  const acksDisplay = useCountUp(confirmedAcks);

  return (
    <>
      {/* Sticky top navigation */}
      <div className="topbar">
        <div className="topbar-inner">
          <div style={{ display: 'flex', alignItems: 'center', gap: '14px', minWidth: 0 }}>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', fontSize: '15px', fontWeight: 700, letterSpacing: '-0.02em' }}>
              <span style={{ width: '8px', height: '8px', borderRadius: '2px', background: 'var(--accent-primary)', display: 'inline-block' }} />
              Lot Zero
            </span>
            <span className="hide-mobile" style={{ color: 'var(--border-medium)' }}>/</span>
            <span className="mono-val hide-mobile" style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>{caseId}</span>
            <span className="status-inline" style={{ fontSize: '12.5px' }}>
              <span className={`status-dot ${sseConnected ? 'status-dot-success' : 'status-dot-danger'}`} />
              {sseConnected ? 'Live' : 'Offline'}
            </span>
          </div>

          <div className="topbar-actions">
            <select
              value={activeApiKey || 'key-recall-coord-01'}
              onChange={(e) => onApiKeyChange && onApiKeyChange(e.target.value)}
              style={{ fontSize: '13px', padding: '6px 10px', maxWidth: '180px' }}
              title="Acting role for signed decisions"
            >
              <option value="key-recall-coord-01">Recall Coordinator</option>
              <option value="key-qa-lead-01">QA Lead</option>
              <option value="key-ops-01">Customer Operations</option>
              <option value="key-closure-auth-01">Closure Authority</option>
              <option value="key-agent-svc-01">Agent Service</option>
            </select>

            <button className="btn btn-ghost" onClick={onExportAudit} disabled={loading} title="Download hash-chained audit bundle">
              <Download size={14} />
              <span className="hide-mobile">Export</span>
            </button>
            <button className="btn btn-ghost" onClick={onOpenHowItWorks} title="Architecture notes">
              <BookOpen size={14} />
              <span className="hide-mobile">Docs</span>
            </button>
            <button className="btn btn-ghost" onClick={onReset} disabled={loading} title="Reset to clean baseline">
              <RefreshCw size={14} />
            </button>
            <button
              className={`btn btn-primary ${!hasSignal && !loading ? 'btn-pulse' : ''}`}
              onClick={onSimulateSignal}
              disabled={loading}
            >
              <Sparkles size={14} />
              Simulate signal
            </button>
          </div>
        </div>
      </div>

      {/* Page header */}
      <div className="page">
        <div className="page-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '12px' }}>
            <span className="status-tag">Evaluation tenant · synthetic records</span>
            <span className="status-tag">{modelName}</span>
          </div>

          <h1 className="page-title">Recall incident workspace</h1>
          <p className="page-subtitle">
            Evidence-backed containment for case {caseId} at EVAL-TENANT-01, Minneapolis.
            Every decision below is signed and appended to a tamper-evident event ledger.
          </p>

          <div className="page-meta">
            {docVersion && (
              <span>
                Source document <strong>{docVersion}</strong>
              </span>
            )}
            {docHash && (
              <span>
                SHA-256 <strong className="mono-val">{String(docHash).substring(0, 12)}…</strong>
              </span>
            )}
            {projection && (
              <span>
                Standing policy{' '}
                <strong style={{ color: isQaApproved ? 'var(--status-success-text)' : 'var(--status-warning-text)' }}>
                  {isQaApproved ? 'AUTH-HOLD-01 · firm quarantine' : 'EVAL-HOLD-01 · provisional soft hold'}
                </strong>
              </span>
            )}
          </div>

          {/* Key numbers — borderless, hairline dividers */}
          <div className="stat-row">
            {unitsHeld !== null && (
              <div className="stat">
                <div className="stat-label">Units on hold</div>
                <div className="stat-value">{unitsDisplay}</div>
              </div>
            )}
            {falseHolds !== null && (
              <div className="stat">
                <div className="stat-label">False holds</div>
                <div className="stat-value">{falseHoldsDisplay}</div>
              </div>
            )}
            {ledgerCount !== null && (
              <div className="stat">
                <div className="stat-label">Ledger events</div>
                <div className="stat-value">{ledgerDisplay}</div>
              </div>
            )}
            {totalAcks > 0 && (
              <div className="stat">
                <div className="stat-label">Consignees confirmed</div>
                <div className="stat-value">
                  {acksDisplay}
                  <small>/ {totalAcks}</small>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
