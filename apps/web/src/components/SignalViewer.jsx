import React, { useState } from 'react';
import { FileText, AlertTriangle, Sparkles, Hash, Lock, CheckCircle2 } from 'lucide-react';

export function SignalViewer({ signal, scopes, modelName }) {
  const [activeCitation, setActiveCitation] = useState(null);

  if (!signal) {
    return (
      <div className="glass-panel" style={{ padding: '20px' }}>
        <h2 style={{ fontSize: '1.1rem', marginBottom: '10px' }}>Safety Signal</h2>
        <p style={{ color: 'var(--text-muted)' }}>No signal loaded yet.</p>
      </div>
    );
  }

  return (
    <div className="glass-panel" style={{ padding: '18px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <FileText size={18} color="var(--accent-cyan)" />
          <h2 style={{ fontSize: '1.05rem', fontWeight: 700 }}>Signal Ingestion & Citations</h2>
        </div>
        <span className="badge badge-amber">
          <AlertTriangle size={12} /> Positive Biohazard
        </span>
      </div>

      {/* Document Digest & Version Header */}
      <div
        style={{
          background: 'rgba(0, 0, 0, 0.4)',
          border: '1px solid var(--border-subtle)',
          borderRadius: '8px',
          padding: '8px 12px',
          fontSize: '0.72rem',
          fontFamily: 'var(--font-mono)',
          color: 'var(--text-secondary)',
          display: 'flex',
          flexDirection: 'column',
          gap: '3px',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <span>DOC: <strong>{signal.doc_version || 'v1.0 (Signed Lab PDF)'}</strong></span>
          <span>SOURCE: <strong>{signal.source_id}</strong></span>
        </div>
        <div style={{ color: 'var(--text-muted)', wordBreak: 'break-all' }}>
          SHA-256: <span style={{ color: 'var(--accent-cyan)' }}>{signal.doc_hash || 'd8f3a9e14417b89...'}</span>
        </div>
      </div>

      {/* Raw Lab Document Container */}
      <div
        style={{
          background: 'rgba(0, 0, 0, 0.5)',
          border: '1px solid var(--border-subtle)',
          borderRadius: '8px',
          padding: '12px',
          fontFamily: 'var(--font-mono)',
          fontSize: '0.78rem',
          lineHeight: '1.55',
          color: '#e2e8f0',
        }}
      >
        <div style={{ color: 'var(--text-muted)', marginBottom: '6px', fontSize: '0.72rem', borderBottom: '1px solid rgba(255,255,255,0.06)', paddingBottom: '4px' }}>
          [OFFICIAL LAB ANALYSIS REPORT - APEX MICRO QUALITY LABS] · SPL-99824
        </div>
        <div>
          SAMPLE ID: {signal.sample_id} | DATE: 2026-08-14 11:42 UTC<br />
          CLIENT: EVAL-TENANT-01 Foods Corp<br />
          TEST ITEM:{' '}
          <span
            className="citation-highlight"
            onClick={() => setActiveCitation(signal.citation_spans[0])}
            title="Click to view citation metadata"
          >
            Raw Ingredient Lot ING-4417 (Organic Wheat Flour)
          </span><br />
          RESULT:{' '}
          <span
            className="citation-highlight"
            onClick={() => setActiveCitation(signal.citation_spans[1])}
            title="Click to view citation metadata"
          >
            POSITIVE for Salmonella enterica serovar Typhimurium
          </span>.<br />
          CONCENTRATION: {signal.cfu_count} (Exceeds regulatory threshold: 0 CFU/25g).<br />
          RECOMMENDATION:{' '}
          <span
            className="citation-highlight"
            onClick={() => setActiveCitation(signal.citation_spans[2])}
            title="Click to view citation metadata"
          >
            Immediate scope isolation of all finished batches utilizing Lot ING-4417
          </span>.
        </div>
      </div>

      {/* Gemini Grounded Extraction Card */}
      <div
        style={{
          background: 'rgba(6, 182, 212, 0.06)',
          border: '1px solid rgba(6, 182, 212, 0.25)',
          borderRadius: '8px',
          padding: '12px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
          <span style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--accent-cyan)', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Sparkles size={13} /> Gemini Grounded Extractions
          </span>
          <span className="badge badge-cyan">{modelName?.includes('Live') ? 'Live GenAI' : 'Replay Grounded'}</span>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '0.78rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(255,255,255,0.05)', paddingBottom: '3px' }}>
            <span style={{ color: 'var(--text-secondary)' }}>Target Ingredient:</span>
            <strong style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent-amber)' }}>ING-4417 (Organic Wheat Flour)</strong>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(255,255,255,0.05)', paddingBottom: '3px' }}>
            <span style={{ color: 'var(--text-secondary)' }}>Hazard Classification:</span>
            <strong style={{ color: 'var(--accent-rose)' }}>Class I Recall (Pathogen)</strong>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(255,255,255,0.05)', paddingBottom: '3px' }}>
            <span style={{ color: 'var(--text-secondary)' }}>Standing Policy Trigger:</span>
            <strong style={{ fontFamily: 'var(--font-mono)' }}>EVAL-HOLD-01 (30m max)</strong>
          </div>
        </div>
      </div>

      {/* Active Citation Inspector */}
      {activeCitation && (
        <div
          style={{
            background: 'rgba(245, 158, 11, 0.08)',
            border: '1px solid var(--border-active)',
            borderRadius: '8px',
            padding: '10px 12px',
            fontSize: '0.75rem',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '3px' }}>
            <span style={{ fontWeight: 700, color: 'var(--accent-amber)' }}>
              Evidence Span: {activeCitation.claim}
            </span>
            <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
              Offsets [{activeCitation.start} - {activeCitation.end}]
            </span>
          </div>
          <div style={{ color: 'var(--text-primary)', fontStyle: 'italic' }}>
            "{activeCitation.text}"
          </div>
        </div>
      )}
    </div>
  );
}
