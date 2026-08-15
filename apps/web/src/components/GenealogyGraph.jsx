import React from 'react';
import { GitBranch, Factory, AlertOctagon, CheckCircle2 } from 'lucide-react';

export function GenealogyGraph({ genealogy, metrics, phase, isQaApproved }) {
  if (!genealogy) return null;

  const isHoldActive = ['provisional_containment', 'action_review', 'ack_monitoring', 'effectiveness_check', 'closed'].includes(phase);

  return (
    <div className="card-panel" style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <div className="section-label" style={{ marginBottom: '2px' }}>Traceability Engine</div>
          <h2 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <GitBranch size={15} style={{ color: 'var(--accent-primary)' }} />
            Bidirectional recall traceability DAG
          </h2>
        </div>
        <div style={{ display: 'flex', gap: '6px' }}>
          <span className="status-tag status-tag-warning">
            <span className="mono-val" style={{ fontWeight: 600 }}>200</span> Units Held
          </span>
          <span className="status-tag status-tag-success">
            <span className="mono-val" style={{ fontWeight: 600 }}>0</span> False Holds
          </span>
        </div>
      </div>

      {/* Metrics Row — Dense Aligned Panel with Numbers Loudest */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px' }}>
        <div style={{ background: 'var(--bg-surface-subtle)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)', padding: '10px 12px' }}>
          <div className="section-label" style={{ fontSize: '10px', marginBottom: '2px' }}>Contaminated Scope</div>
          <div className="mono-val" style={{ fontSize: '18px', fontWeight: 600, color: 'var(--text-primary)' }}>
            200 <span style={{ fontSize: '12px', fontWeight: 400, color: 'var(--text-muted)' }}>units (2 batches)</span>
          </div>
        </div>

        <div style={{ background: 'var(--bg-surface-subtle)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)', padding: '10px 12px' }}>
          <div className="section-label" style={{ fontSize: '10px', marginBottom: '2px' }}>Containment Status</div>
          <div style={{ fontSize: '14px', fontWeight: 600, color: isQaApproved ? 'var(--status-success-text)' : (isHoldActive ? 'var(--status-warning-text)' : 'var(--text-muted)'), marginTop: '2px' }}>
            {isQaApproved ? 'Firm Quarantine' : (isHoldActive ? 'Soft Hold (30m)' : 'Pending Eval')}
          </div>
        </div>

        <div style={{ background: 'var(--bg-surface-subtle)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)', padding: '10px 12px' }}>
          <div className="section-label" style={{ fontSize: '10px', marginBottom: '2px' }}>Control Validation</div>
          <div className="mono-val" style={{ fontSize: '18px', fontWeight: 600, color: 'var(--status-success-text)' }}>
            0 <span style={{ fontSize: '12px', fontWeight: 400, color: 'var(--text-muted)' }}>FP-100-ADJ held</span>
          </div>
        </div>
      </div>

      {/* Interactive Visual Graph Nodes */}
      <div
        style={{
          background: 'var(--bg-input)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--radius-md)',
          padding: '14px',
          display: 'flex',
          flexDirection: 'column',
          gap: '10px',
        }}
      >
        {/* Step 1: Upstream Supplier Intake */}
        <div style={{ display: 'flex', justifyContent: 'center' }}>
          <div
            style={{
              background: 'var(--bg-surface)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-md)',
              padding: '8px 12px',
              maxWidth: '420px',
              width: '100%',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}
          >
            <div>
              <div className="section-label" style={{ fontSize: '10px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                <Factory size={11} /> Upstream Supplier Intake
              </div>
              <div className="mono-val" style={{ fontWeight: 600, fontSize: '13px', color: 'var(--text-primary)', marginTop: '2px' }}>
                SUP-MILLER-2026-08 (Miller Mills)
              </div>
            </div>
            <span className="status-tag" style={{ fontSize: '11px' }}>
              Grain Silo 4
            </span>
          </div>
        </div>

        <div style={{ textAlign: 'center', color: 'var(--text-muted)', fontSize: '11px' }}>
          ↓ Milling & lot allocation
        </div>

        {/* Step 2: Contaminated Ingredient Root */}
        <div style={{ display: 'flex', justifyContent: 'center' }}>
          <div
            style={{
              background: 'var(--status-danger-subtle)',
              border: '1px solid rgba(239, 68, 68, 0.3)',
              borderRadius: 'var(--radius-md)',
              padding: '8px 12px',
              maxWidth: '420px',
              width: '100%',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2px' }}>
              <span className="status-tag status-tag-danger" style={{ fontSize: '11px', padding: '1px 6px' }}>
                <span className="status-dot status-dot-danger" />
                Contaminated Lot
              </span>
              <span style={{ fontSize: '11px', color: 'var(--status-danger-text)' }}>Salmonella Enterica</span>
            </div>
            <div className="mono-val" style={{ fontWeight: 600, fontSize: '13px', color: 'var(--text-primary)' }}>
              ING-4417 (Organic Wheat Flour)
            </div>
          </div>
        </div>

        <div style={{ textAlign: 'center', color: 'var(--text-muted)', fontSize: '11px' }}>
          ↓ Packaging lines 2 & 3
        </div>

        {/* Step 3: Finished Goods Batches & Negative Control */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: '8px' }}>
          {/* Batch A */}
          <div
            style={{
              background: isHoldActive ? 'var(--status-warning-subtle)' : 'var(--bg-surface)',
              border: `1px solid ${isHoldActive ? 'rgba(245, 158, 11, 0.3)' : 'var(--border-subtle)'}`,
              borderRadius: 'var(--radius-md)',
              padding: '10px',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
              <span className="section-label" style={{ fontSize: '10px' }}>Line 2 Batch</span>
              <span className="mono-val" style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>120 units</span>
            </div>
            <div className="mono-val" style={{ fontWeight: 600, fontSize: '13px', color: 'var(--text-primary)' }}>
              FP-100-L240814-A
            </div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
              Finished Cereal 500g
            </div>
            {isHoldActive && (
              <div style={{ marginTop: '6px', fontSize: '11px', color: isQaApproved ? 'var(--status-success-text)' : 'var(--status-warning-text)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                <span className={`status-dot ${isQaApproved ? 'status-dot-success' : 'status-dot-warning'}`} />
                {isQaApproved ? 'Firm Quarantine Locked' : 'Provisional Soft Hold'}
              </div>
            )}
          </div>

          {/* Batch B */}
          <div
            style={{
              background: isHoldActive ? 'var(--status-warning-subtle)' : 'var(--bg-surface)',
              border: `1px solid ${isHoldActive ? 'rgba(245, 158, 11, 0.3)' : 'var(--border-subtle)'}`,
              borderRadius: 'var(--radius-md)',
              padding: '10px',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
              <span className="section-label" style={{ fontSize: '10px' }}>Line 3 Batch</span>
              <span className="mono-val" style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>80 units</span>
            </div>
            <div className="mono-val" style={{ fontWeight: 600, fontSize: '13px', color: 'var(--text-primary)' }}>
              FP-100-L240814-B
            </div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
              Finished Cereal 500g
            </div>
            {isHoldActive && (
              <div style={{ marginTop: '6px', fontSize: '11px', color: isQaApproved ? 'var(--status-success-text)' : 'var(--status-warning-text)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                <span className={`status-dot ${isQaApproved ? 'status-dot-success' : 'status-dot-warning'}`} />
                {isQaApproved ? 'Firm Quarantine Locked' : 'Provisional Soft Hold'}
              </div>
            )}
          </div>

          {/* Negative Control Batch */}
          <div
            style={{
              background: 'var(--status-success-subtle)',
              border: '1px solid rgba(34, 197, 94, 0.25)',
              borderRadius: 'var(--radius-md)',
              padding: '10px',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
              <span className="section-label" style={{ fontSize: '10px' }}>Clean Control</span>
              <span className="mono-val" style={{ fontSize: '11px', color: 'var(--status-success-text)' }}>0 held</span>
            </div>
            <div className="mono-val" style={{ fontWeight: 600, fontSize: '13px', color: 'var(--text-primary)' }}>
              FP-100-ADJ
            </div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
              Adjacent Clean Batch (Lot ING-4418)
            </div>
            <div style={{ marginTop: '6px', fontSize: '11px', color: 'var(--status-success-text)', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <span className="status-dot status-dot-success" />
              Verified Negative
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
