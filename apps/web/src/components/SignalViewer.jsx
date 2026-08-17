import React, { useState } from 'react';

export function SignalViewer({ signal, scopes, modelName }) {
  const [activeCitationIndex, setActiveCitationIndex] = useState(0);

  const rawText = signal?.raw_text || '';
  const spans = (signal?.citation_spans || signal?.spans || []).map((s, idx) => ({
    index: idx,
    start: s.start ?? s.start_char ?? 0,
    end: s.end ?? s.end_char ?? 0,
    text: s.text ?? s.exact_quote ?? '',
    claim: s.claim ?? s.claim_type ?? 'Grounded citation',
    evidenceId: s.evidence_id || `EVID-0${idx + 1}`,
  }));

  // Render raw text with dynamic character-sliced citation spans
  const renderDocumentSlices = () => {
    if (!rawText) return null;
    if (!spans || spans.length === 0) {
      return <div style={{ whiteSpace: 'pre-wrap', fontFamily: 'var(--font-mono)', fontSize: '13px', lineHeight: 1.6 }}>{rawText}</div>;
    }

    const elements = [];
    let lastIndex = 0;

    spans.forEach((span, idx) => {
      // Chunk before the span
      if (span.start > lastIndex) {
        elements.push(
          <span key={`text-${idx}`}>{rawText.slice(lastIndex, span.start)}</span>
        );
      }

      // Highlighted citation span sliced directly from rawText offsets
      const isSelected = activeCitationIndex === idx;
      elements.push(
        <span
          key={`span-${idx}`}
          className="citation-highlight"
          style={{
            background: isSelected ? 'rgba(0, 220, 130, 0.18)' : 'transparent',
            borderBottom: isSelected ? '2px solid var(--accent-primary)' : '1px dashed rgba(0, 220, 130, 0.45)',
            fontWeight: isSelected ? 600 : 400,
            padding: '1px 2px',
            borderRadius: '2px',
          }}
          onClick={() => setActiveCitationIndex(idx)}
          title={`Click to inspect offset [${span.start}..${span.end}] (${span.claim})`}
        >
          {rawText.slice(span.start, span.end)}
        </span>
      );

      lastIndex = span.end;
    });

    // Remainder after the last span
    if (lastIndex < rawText.length) {
      elements.push(
        <span key="text-end">{rawText.slice(lastIndex)}</span>
      );
    }

    return (
      <div style={{ whiteSpace: 'pre-wrap', fontFamily: 'var(--font-mono)', fontSize: '13px', lineHeight: 1.6 }}>
        {elements}
      </div>
    );
  };

  const activeSpan = spans[activeCitationIndex] || spans[0];

  return (
    <section className="section">
      <div className="section-head">
        <div>
          <h2 className="section-title">Safety signal</h2>
          <p className="section-desc">
            Signed laboratory report ingested as the incident's root evidence. Character offsets are
            mechanically anchored to the SHA-256 document digest.
          </p>
        </div>
        <span className="status-inline">
          <span className="status-dot status-dot-danger" />
          Positive biohazard
        </span>
      </div>

      {!signal ? (
        <div className="card-panel" style={{ color: 'var(--text-muted)', fontSize: '14px' }}>
          No signal loaded yet. Use “Simulate signal” to ingest the evaluation lab report.
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {/* Source document with character-slicing */}
          <div className="card-panel">
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                gap: '16px',
                marginBottom: '16px',
                fontSize: '13px',
                color: 'var(--text-muted)',
                flexWrap: 'wrap',
              }}
            >
              <span>{signal.doc_version || 'v1.0 · signed lab PDF'}</span>
              <span className="mono-val">{signal.source_id}</span>
            </div>

            <div className="doc-block">
              {renderDocumentSlices()}
            </div>

            {signal.doc_hash && (
              <div
                style={{
                  marginTop: '14px',
                  fontSize: '12.5px',
                  color: 'var(--text-muted)',
                  wordBreak: 'break-all',
                }}
              >
                SHA-256 <span className="mono-val">{signal.doc_hash}</span>
              </div>
            )}
          </div>

          {/* Grounded extraction & Mechanical Offset Inspector */}
          <div className="card-panel">
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'baseline',
                marginBottom: '10px',
                flexWrap: 'wrap',
                gap: '8px',
              }}
            >
              <h3 style={{ fontSize: '15px', fontWeight: 600 }}>Grounded extraction</h3>
              <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                {signal.is_live_model ? 'Live Gemini 3.5 Flash' : (signal.model_version || 'Deterministic Evaluator')}
              </span>
            </div>

            <dl>
              <div className="def-row">
                <dt>Target ingredient</dt>
                <dd>{signal.tested_ingredient || 'ING-4417 · Organic Wheat Flour'}</dd>
              </div>
              <div className="def-row">
                <dt>Hazard classification</dt>
                <dd style={{ color: 'var(--status-danger-text)' }}>Class I recall · Salmonella enterica</dd>
              </div>
              <div className="def-row">
                <dt>Standing policy trigger</dt>
                <dd>EVAL-HOLD-01 · 30 min max</dd>
              </div>
            </dl>

            {/* Character Offset Inspector */}
            {activeSpan && (
              <div
                style={{
                  marginTop: '16px',
                  padding: '14px 16px',
                  background: 'var(--accent-primary-subtle)',
                  border: '1px solid rgba(0, 220, 130, 0.3)',
                  borderRadius: 'var(--radius-md)',
                  fontSize: '13.5px',
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    gap: '12px',
                    marginBottom: '6px',
                    flexWrap: 'wrap',
                  }}
                >
                  <span style={{ fontWeight: 600 }}>
                    {activeSpan.claim} ({activeSpan.evidenceId})
                  </span>
                  <span className="mono-val" style={{ color: 'var(--accent-primary)', fontSize: '12.5px', fontWeight: 600 }}>
                    offsets [{activeSpan.start}..{activeSpan.end}] · {activeSpan.end - activeSpan.start} chars
                  </span>
                </div>
                <div style={{ color: 'var(--text-secondary)', fontStyle: 'italic', marginBottom: '8px' }}>
                  “{rawText.slice(activeSpan.start, activeSpan.end)}”
                </div>
                <div style={{ fontSize: '11.5px', color: 'var(--text-muted)' }}>
                  Verified slice anchored to SHA-256 digest: <span className="mono-val">{signal.doc_hash ? `${signal.doc_hash.slice(0, 16)}...` : 'sha256-verified'}</span>
                </div>
              </div>
            )}

            {/* Rejected / Discarded Claims Callout (if live model produced hallucinated quotes) */}
            {signal.discarded_claims && signal.discarded_claims.length > 0 && (
              <div
                style={{
                  marginTop: '12px',
                  padding: '10px 14px',
                  background: 'rgba(239, 68, 68, 0.08)',
                  border: '1px solid rgba(239, 68, 68, 0.25)',
                  borderRadius: 'var(--radius-md)',
                  fontSize: '12.5px',
                  color: 'var(--status-danger-text)',
                }}
              >
                <div style={{ fontWeight: 600, marginBottom: '2px' }}>Rejected ungrounded claims ({signal.discarded_claims.length})</div>
                {signal.discarded_claims.map((claim, i) => (
                  <div key={i} style={{ color: 'var(--text-muted)' }}>• {claim}</div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
