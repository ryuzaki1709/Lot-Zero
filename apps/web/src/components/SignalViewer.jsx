import React, { useState } from 'react';
import { FileText, AlertCircle, Sparkles } from 'lucide-react';

export function SignalViewer({ signal, scopes, modelName }) {
  const [activeCitation, setActiveCitation] = useState(null);

  if (!signal) {
    return (
      <div className="card-panel" style={{ padding: '16px' }}>
        <div className="section-label" style={{ marginBottom: '4px' }}>Safety Signal</div>
        <h2 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)' }}>Laboratory notice</h2>
        <p style={{ color: 'var(--text-muted)', fontSize: '13px', marginTop: '8px' }}>No signal loaded yet.</p>
      </div>
    );
  }

  return (
    <div className="card-panel" style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <div className="section-label" style={{ marginBottom: '2px' }}>Safety Signal Ingestion</div>
          <h2 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <FileText size={15} style={{ color: 'var(--accent-primary)' }} />
            Laboratory inspection report
          </h2>
        </div>
        <span className="status-tag status-tag-warning">
          <span className="status-dot status-dot-warning" />
          Positive Biohazard
        </span>
      </div>

      {/* Document Digest & Provenance Header */}
      <div
        style={{
          background: 'var(--bg-surface-subtle)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--radius-md)',
          padding: '8px 10px',
          fontSize: '12px',
          display: 'flex',
          flexDirection: 'column',
          gap: '4px',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <span style={{ color: 'var(--text-muted)' }}>
            Doc: <strong style={{ color: 'var(--text-secondary)' }}>{signal.doc_version || 'v1.0 (Signed Lab PDF)'}</strong>
          </span>
          <span style={{ color: 'var(--text-muted)' }}>
            Source: <strong style={{ color: 'var(--text-secondary)' }}>{signal.source_id}</strong>
          </span>
        </div>
        <div style={{ color: 'var(--text-muted)', wordBreak: 'break-all' }}>
          SHA-256: <code className="mono-val" style={{ color: 'var(--text-secondary)' }}>{signal.doc_hash || 'd8f3a9e14417b89...'}</code>
        </div>
      </div>

      {/* Raw Lab Document Container with Citation Highlights */}
      <div
        style={{
          background: 'var(--bg-input)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--radius-md)',
          padding: '10px 12px',
          fontFamily: 'var(--font-mono)',
          fontSize: '12px',
          lineHeight: '1.6',
          color: 'var(--text-primary)',
        }}
      >
        <div style={{ color: 'var(--text-muted)', marginBottom: '6px', fontSize: '11px', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '4px' }}>
          [APEX MICRO QUALITY LABS ANALYSIS REPORT] · SPL-99824
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
          background: 'var(--bg-surface-subtle)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--radius-md)',
          padding: '10px 12px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
          <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Sparkles size={12} style={{ color: 'var(--accent-primary)' }} />
            Grounded Extractions
          </span>
          <span className="status-tag" style={{ fontSize: '11px', padding: '1px 6px' }}>
            {modelName?.includes('Live') ? 'Live GenAI' : 'Replay Grounded'}
          </span>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '12px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '3px' }}>
            <span style={{ color: 'var(--text-muted)' }}>Target Ingredient:</span>
            <span className="mono-val" style={{ color: 'var(--text-primary)', fontWeight: 500 }}>
              ING-4417 (Organic Wheat Flour)
            </span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '3px' }}>
            <span style={{ color: 'var(--text-muted)' }}>Hazard Classification:</span>
            <span style={{ color: 'var(--status-danger-text)', fontWeight: 500 }}>
              Class I Recall (Pathogen)
            </span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ color: 'var(--text-muted)' }}>Standing Policy Trigger:</span>
            <span className="mono-val" style={{ color: 'var(--text-secondary)' }}>
              EVAL-HOLD-01 (30m max)
            </span>
          </div>
        </div>
      </div>

      {/* Active Citation Inspector */}
      {activeCitation && (
        <div
          style={{
            background: 'var(--accent-primary-subtle)',
            border: '1px solid var(--accent-primary)',
            borderRadius: 'var(--radius-md)',
            padding: '8px 10px',
            fontSize: '12px',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '2px' }}>
            <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
              Citation: {activeCitation.claim}
            </span>
            <span className="mono-val" style={{ color: 'var(--text-muted)', fontSize: '11px' }}>
              Offsets [{activeCitation.start} - {activeCitation.end}]
            </span>
          </div>
          <div style={{ color: 'var(--text-secondary)', fontSize: '11px', fontStyle: 'italic' }}>
            "{activeCitation.text}"
          </div>
        </div>
      )}
    </div>
  );
}
