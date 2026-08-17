import React from 'react';

export function GenealogyGraph({ genealogy, metrics, phase, isQaApproved }) {
  if (!genealogy || !Array.isArray(genealogy.nodes) || genealogy.nodes.length === 0) {
    return (
      <section className="section">
        <div className="section-head">
          <div>
            <h2 className="section-title">Traceability</h2>
            <p className="section-desc">
              Bidirectional genealogy from supplier intake to finished goods. Awaiting safety signal.
            </p>
          </div>
        </div>
        <div className="card-panel" style={{ padding: '32px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '13.5px' }}>
          No active recall scope. Simulate a safety signal to generate the production genealogy DAG.
        </div>
      </section>
    );
  }

  const isHoldActive = [
    'provisional_containment',
    'action_review',
    'ack_monitoring',
    'effectiveness_check',
    'closed',
  ].includes(phase);
  const holdLabel = isQaApproved ? 'Firm quarantine' : 'Provisional soft hold';

  const supplierNode = genealogy.nodes.find((n) => n.type === 'supplier_origin');
  const ingredientNode = genealogy.nodes.find((n) => n.type === 'ingredient');
  const finishedNodes = genealogy.nodes.filter((n) => n.type === 'finished_product');
  const controlNode = genealogy.nodes.find((n) => n.type === 'unaffected_batch');

  const nodeStyle = {
    border: '1px solid var(--border-subtle)',
    borderRadius: 'var(--radius-lg)',
    padding: '16px 20px',
    background: 'var(--bg-surface)',
  };

  const arrow = (label) => (
    <div style={{ display: 'flex', alignItems: 'center', gap: '10px', padding: '10px 0 10px 20px' }}>
      <div style={{ width: '1px', height: '28px', background: 'var(--border-medium)' }} />
      {label && <span style={{ fontSize: '12.5px', color: 'var(--text-muted)' }}>{label}</span>}
    </div>
  );

  return (
    <section className="section">
      <div className="section-head">
        <div>
          <h2 className="section-title">Traceability</h2>
          <p className="section-desc">
            Bidirectional genealogy from supplier intake to finished goods. The adjacent clean batch is
            traced as a negative control — zero false holds proves scope precision.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '20px', fontSize: '13px', color: 'var(--text-secondary)' }}>
          {metrics?.provisional_hold_quantity !== undefined && (
            <span>
              <strong style={{ color: 'var(--text-primary)', fontVariantNumeric: 'tabular-nums' }}>
                {metrics.provisional_hold_quantity}
              </strong>{' '}
              units held
            </span>
          )}
          {metrics?.unaffected_hold_quantity !== undefined && (
            <span>
              <strong style={{ color: 'var(--text-primary)', fontVariantNumeric: 'tabular-nums' }}>
                {metrics.unaffected_hold_quantity}
              </strong>{' '}
              false holds
            </span>
          )}
          <span
            style={{
              color: isQaApproved
                ? 'var(--status-success-text)'
                : isHoldActive
                ? 'var(--status-warning-text)'
                : 'var(--text-muted)',
            }}
          >
            {isQaApproved
              ? 'Firm quarantine'
              : isHoldActive
              ? 'Soft hold · 30 min'
              : 'Pending evaluation'}
          </span>
        </div>
      </div>

      <div className="card-panel" style={{ overflowX: 'auto' }}>
        {/* Supplier Node */}
        {supplierNode && (
          <div
            style={{
              ...nodeStyle,
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              gap: '16px',
              flexWrap: 'wrap',
            }}
          >
            <div>
              <div style={{ fontSize: '12.5px', color: 'var(--text-muted)', marginBottom: '3px' }}>
                Upstream supplier intake {supplierNode.source_facility ? `· ${supplierNode.source_facility}` : ''}
              </div>
              <div style={{ fontSize: '15px', fontWeight: 600 }}>
                {supplierNode.label || supplierNode.id}{' '}
                {supplierNode.id && (
                  <span className="mono-val" style={{ color: 'var(--text-muted)', fontWeight: 400, marginLeft: '6px' }}>
                    {supplierNode.id}
                  </span>
                )}
              </div>
            </div>
            {supplierNode.status && (
              <span style={{ fontSize: '13px', color: 'var(--text-muted)', textTransform: 'capitalize' }}>
                {supplierNode.status}
              </span>
            )}
          </div>
        )}

        {arrow('Milling & lot allocation')}

        {/* Contaminated Ingredient Node */}
        {ingredientNode && (
          <div
            style={{
              ...nodeStyle,
              borderColor: 'rgba(248, 113, 113, 0.35)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              gap: '16px',
              flexWrap: 'wrap',
            }}
          >
            <div>
              <div
                className="status-inline"
                style={{ marginBottom: '3px', fontSize: '12.5px', color: 'var(--status-danger-text)' }}
              >
                <span className="status-dot status-dot-danger" />
                Contaminated lot {ingredientNode.hazard ? `· ${ingredientNode.hazard}` : ''}
              </div>
              <div style={{ fontSize: '15px', fontWeight: 600 }}>
                {ingredientNode.label || ingredientNode.id}{' '}
                {ingredientNode.id && (
                  <span className="mono-val" style={{ color: 'var(--text-muted)', fontWeight: 400, marginLeft: '6px' }}>
                    {ingredientNode.id}
                  </span>
                )}
              </div>
            </div>
          </div>
        )}

        {arrow('Packaging lines')}

        {/* Downstream batches */}
        <div className="grid-auto-xs">
          {finishedNodes.map((b) => {
            const isReleased = b.hold_status === 'released_negative_retest';
            const isQuarantined = b.hold_status === 'quarantine_active';
            const isSoftHold = b.hold_status === 'soft_hold_active';
            return (
              <div key={b.id} style={{ ...nodeStyle }}>
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    fontSize: '12.5px',
                    color: 'var(--text-muted)',
                    marginBottom: '6px',
                  }}
                >
                  <span>{b.line || 'Finished batch'}</span>
                  {b.quantity !== undefined && (
                    <span style={{ fontVariantNumeric: 'tabular-nums' }}>{b.quantity} units</span>
                  )}
                </div>
                <div className="mono-val" style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)' }}>
                  {b.id}
                </div>
                {isHoldActive && (
                  <div
                    className="status-inline"
                    style={{
                      marginTop: '10px',
                      fontSize: '12.5px',
                      color: isReleased
                        ? 'var(--status-success-text)'
                        : isQuarantined
                        ? 'var(--status-success-text)'
                        : isSoftHold
                        ? 'var(--status-warning-text)'
                        : 'var(--text-muted)',
                    }}
                  >
                    <span
                      className={`status-dot ${
                        isReleased || isQuarantined ? 'status-dot-success' : 'status-dot-warning'
                      }`}
                    />
                    {isReleased ? 'Released (Negative Re-test)' : holdLabel}
                  </div>
                )}
              </div>
            );
          })}

          {/* Negative Control Node */}
          {controlNode && (
            <div style={{ ...nodeStyle, borderColor: 'rgba(52, 211, 153, 0.3)' }}>
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  fontSize: '12.5px',
                  color: 'var(--text-muted)',
                  marginBottom: '6px',
                }}
              >
                <span>{controlNode.label || 'Negative control'}</span>
                <span style={{ fontVariantNumeric: 'tabular-nums' }}>0 held</span>
              </div>
              <div className="mono-val" style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)' }}>
                {controlNode.id}
              </div>
              <div
                className="status-inline"
                style={{ marginTop: '10px', fontSize: '12.5px', color: 'var(--status-success-text)' }}
              >
                <span className="status-dot status-dot-success" />
                Verified negative — released
              </div>
            </div>
          )}
        </div>

        {/* Unresolved Genealogy Boundaries Notice */}
        {genealogy.unresolved_edges && genealogy.unresolved_edges.length > 0 && (
          <div
            style={{
              marginTop: '16px',
              padding: '12px 16px',
              background: 'rgba(234, 179, 8, 0.08)',
              border: '1px solid rgba(234, 179, 8, 0.25)',
              borderRadius: 'var(--radius-md)',
              fontSize: '13px',
              color: 'var(--status-warning-text)',
            }}
          >
            <div style={{ fontWeight: 600, marginBottom: '4px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span className="status-dot status-dot-warning" />
              Traceability boundary notice (Incomplete downstream path)
            </div>
            {genealogy.unresolved_edges.map((e) => (
              <div key={e.edge_id} style={{ color: 'var(--text-secondary)', marginTop: '4px' }}>
                Edge <span className="mono-val">{e.edge_id}</span> ({e.source_id} &rarr;{' '}
                <span className="mono-val">{e.target_id}</span>) terminates at an unmapped transform node without finished product records. This boundary is recorded in the cryptographic audit trail and does not alter the verified hold scope.
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
