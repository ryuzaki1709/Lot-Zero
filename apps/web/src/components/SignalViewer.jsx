import React, { useState } from 'react';

export function SignalViewer({ signal, scopes, modelName }) {
  const [activeCitation, setActiveCitation] = useState(null);

  return (
    <section className="section">
      <div className="section-head">
        <div>
          <h2 className="section-title">Safety signal</h2>
          <p className="section-desc">
            Signed laboratory report ingested as the incident's root evidence. Underlined passages are
            grounded citations — click one to inspect its exact character offsets.
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
          {/* Source document */}
          <div className="card-panel">
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: '16px', marginBottom: '16px', fontSize: '13px', color: 'var(--text-muted)', flexWrap: 'wrap' }}>
              <span>{signal.doc_version || 'v1.0 · signed lab PDF'}</span>
              <span className="mono-val">{signal.source_id}</span>
            </div>

            <div className="doc-block">
              <div style={{ color: 'var(--text-muted)', marginBottom: '12px', paddingBottom: '10px', borderBottom: '1px solid var(--border-subtle)' }}>
                Apex Micro Quality Labs · analysis report SPL-99824
              </div>
              SAMPLE ID: {signal.sample_id} · 2026-08-14 11:42 UTC<br />
              CLIENT: EVAL-TENANT-01 Foods Corp<br />
              TEST ITEM:{' '}
              <span className="citation-highlight" onClick={() => setActiveCitation(signal.citation_spans[0])}>
                Raw Ingredient Lot ING-4417 (Organic Wheat Flour)
              </span>
              <br />
              RESULT:{' '}
              <span className="citation-highlight" onClick={() => setActiveCitation(signal.citation_spans[1])}>
                POSITIVE for Salmonella enterica serovar Typhimurium
              </span>
              <br />
              CONCENTRATION: {signal.cfu_count} — exceeds regulatory threshold of 0 CFU/25g<br />
              RECOMMENDATION:{' '}
              <span className="citation-highlight" onClick={() => setActiveCitation(signal.citation_spans[2])}>
                Immediate scope isolation of all finished batches utilizing Lot ING-4417
              </span>
            </div>

            {signal.doc_hash && (
              <div style={{ marginTop: '14px', fontSize: '12.5px', color: 'var(--text-muted)', wordBreak: 'break-all' }}>
                SHA-256 <span className="mono-val">{signal.doc_hash}</span>
              </div>
            )}
          </div>

          {/* Grounded extraction */}
          <div className="card-panel">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: '10px' }}>
              <h3 style={{ fontSize: '15px', fontWeight: 600 }}>Grounded extraction</h3>
              <span style={{ fontSize: '12.5px', color: 'var(--text-muted)' }}>
                {modelName?.includes('Live') ? 'Live GenAI' : 'Replay grounded'}
              </span>
            </div>

            <dl>
              <div className="def-row">
                <dt>Target ingredient</dt>
                <dd>ING-4417 · Organic Wheat Flour</dd>
              </div>
              <div className="def-row">
                <dt>Hazard classification</dt>
                <dd style={{ color: 'var(--status-danger-text)' }}>Class I recall · pathogen</dd>
              </div>
              <div className="def-row">
                <dt>Standing policy trigger</dt>
                <dd>EVAL-HOLD-01 · 30 min max</dd>
              </div>
            </dl>

            {activeCitation && (
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
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', marginBottom: '6px', flexWrap: 'wrap' }}>
                  <span style={{ fontWeight: 600 }}>{activeCitation.claim}</span>
                  <span className="mono-val" style={{ color: 'var(--text-muted)', fontSize: '12px' }}>
                    offsets {activeCitation.start}–{activeCitation.end}
                  </span>
                </div>
                <div style={{ color: 'var(--text-secondary)', fontStyle: 'italic' }}>
                  “{activeCitation.text}”
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
