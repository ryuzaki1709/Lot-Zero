import React from 'react';
import { GitBranch, Box, CheckCircle, AlertOctagon, HelpCircle, ShieldCheck, ArrowDown, Factory } from 'lucide-react';

export function GenealogyGraph({ genealogy, metrics, phase, isQaApproved }) {
  if (!genealogy) return null;

  const isHoldActive = ['provisional_containment', 'action_review', 'ack_monitoring', 'effectiveness_check', 'closed'].includes(phase);

  return (
    <div className="glass-panel" style={{ padding: '18px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <GitBranch size={18} color="var(--accent-cyan)" />
          <h2 style={{ fontSize: '1.05rem', fontWeight: 700 }}>Bidirectional Recall Traceability Graph</h2>
        </div>
        <div style={{ display: 'flex', gap: '6px' }}>
          <span className="badge badge-rose">200 Units Held</span>
          <span className="badge badge-emerald">0 False Holds</span>
        </div>
      </div>

      {/* Metrics Row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px' }}>
        <div style={{ background: 'rgba(0,0,0,0.3)', border: '1px solid var(--border-subtle)', borderRadius: '8px', padding: '8px 10px' }}>
          <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>DOWNSTREAM CONTAMINATED</div>
          <div style={{ fontSize: '1rem', fontWeight: 800, color: 'var(--accent-amber)', fontFamily: 'var(--font-mono)' }}>
            2 Batches (200 Units)
          </div>
        </div>
        <div style={{ background: 'rgba(0,0,0,0.3)', border: '1px solid var(--border-subtle)', borderRadius: '8px', padding: '8px 10px' }}>
          <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>CONTAINMENT REGIME</div>
          <div style={{ fontSize: '0.95rem', fontWeight: 800, color: isQaApproved ? 'var(--accent-emerald)' : (isHoldActive ? 'var(--accent-rose)' : 'var(--text-muted)'), fontFamily: 'var(--font-mono)' }}>
            {isQaApproved ? 'FIRM QUARANTINE' : (isHoldActive ? 'SOFT HOLD (30m)' : 'PENDING EVAL')}
          </div>
        </div>
        <div style={{ background: 'rgba(0,0,0,0.3)', border: '1px solid var(--border-subtle)', borderRadius: '8px', padding: '8px 10px' }}>
          <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>NEGATIVE CONTROL BATCH</div>
          <div style={{ fontSize: '1rem', fontWeight: 800, color: 'var(--accent-emerald)', fontFamily: 'var(--font-mono)' }}>
            FP-100-ADJ (0 Held)
          </div>
        </div>
      </div>

      {/* Interactive Visual Graph Nodes */}
      <div
        style={{
          background: 'rgba(0, 0, 0, 0.45)',
          border: '1px solid var(--border-subtle)',
          borderRadius: '8px',
          padding: '14px',
          display: 'flex',
          flexDirection: 'column',
          gap: '12px',
        }}
      >
        {/* Step 1: Upstream Supplier Intake */}
        <div style={{ display: 'flex', justifyContent: 'center' }}>
          <div
            style={{
              background: 'rgba(15, 23, 42, 0.8)',
              border: '1px solid rgba(255, 255, 255, 0.15)',
              borderRadius: '8px',
              padding: '8px 14px',
              maxWidth: '380px',
              width: '100%',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}
          >
            <div>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                <Factory size={12} /> UPSTREAM SUPPLIER INTAKE (GRAIN SILO 4)
              </div>
              <div style={{ fontWeight: 700, fontSize: '0.82rem', fontFamily: 'var(--font-mono)', color: '#f8fafc' }}>
                SUP-MILLER-2026-08 (Miller Mills)
              </div>
            </div>
            <span className="badge badge-cyan">Origin Investigated</span>
          </div>
        </div>

        <div style={{ textAlign: 'center', color: 'var(--accent-cyan)', fontSize: '0.72rem', fontWeight: 700 }}>
          ↓ Raw Milling & Quality Sampling ↓
        </div>

        {/* Step 2: Ingredient Root */}
        <div style={{ display: 'flex', justifyContent: 'center' }}>
          <div
            style={{
              background: 'rgba(239, 68, 68, 0.12)',
              border: '1px solid rgba(239, 68, 68, 0.5)',
              borderRadius: '8px',
              padding: '10px 16px',
              maxWidth: '380px',
              width: '100%',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2px' }}>
              <span className="badge badge-rose">Contaminated Lot</span>
              <span style={{ fontSize: '0.72rem', color: 'var(--accent-rose)' }}>Salmonella Enterica</span>
            </div>
            <div style={{ fontWeight: 800, fontSize: '0.92rem', fontFamily: 'var(--font-mono)' }}>
              ING-4417 (Organic Wheat Flour)
            </div>
          </div>
        </div>

        <div style={{ textAlign: 'center', color: 'var(--accent-cyan)', fontSize: '0.72rem', fontWeight: 700 }}>
          ↓ Traversed Production Lines (Line 2 & Line 3) ↓
        </div>

        {/* Step 3: Finished Goods Batches & Negative Control */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '10px' }}>
          {/* Batch A */}
          <div
            style={{
              background: isHoldActive ? 'rgba(245, 158, 11, 0.1)' : 'rgba(255, 255, 255, 0.03)',
              border: isHoldActive ? '1px solid rgba(245, 158, 11, 0.4)' : '1px solid var(--border-subtle)',
              borderRadius: '8px',
              padding: '10px',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '3px' }}>
              <span className="badge badge-amber">Batch A (Line 2)</span>
              <span style={{ fontSize: '0.72rem', fontFamily: 'var(--font-mono)' }}>120 Qty</span>
            </div>
            <div style={{ fontWeight: 700, fontSize: '0.82rem', fontFamily: 'var(--font-mono)' }}>
              FP-100-L240814-A
            </div>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', marginTop: '2px' }}>
              Finished Cereal 500g
            </div>
            {isHoldActive && (
              <div style={{ marginTop: '6px', fontSize: '0.7rem', color: isQaApproved ? 'var(--accent-emerald)' : 'var(--accent-amber)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                <AlertOctagon size={12} /> {isQaApproved ? 'Firm Quarantine Locked' : 'Provisional Soft Hold'}
              </div>
            )}
          </div>

          {/* Batch B */}
          <div
            style={{
              background: isHoldActive ? 'rgba(245, 158, 11, 0.1)' : 'rgba(255, 255, 255, 0.03)',
              border: isHoldActive ? '1px solid rgba(245, 158, 11, 0.4)' : '1px solid var(--border-subtle)',
              borderRadius: '8px',
              padding: '10px',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '3px' }}>
              <span className="badge badge-amber">Batch B (Line 3)</span>
              <span style={{ fontSize: '0.72rem', fontFamily: 'var(--font-mono)' }}>80 Qty</span>
            </div>
            <div style={{ fontWeight: 700, fontSize: '0.82rem', fontFamily: 'var(--font-mono)' }}>
              FP-100-L240814-B
            </div>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', marginTop: '2px' }}>
              Finished Cereal 500g
            </div>
            {isHoldActive && (
              <div style={{ marginTop: '6px', fontSize: '0.7rem', color: isQaApproved ? 'var(--accent-emerald)' : 'var(--accent-amber)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                <AlertOctagon size={12} /> {isQaApproved ? 'Firm Quarantine Locked' : 'Provisional Soft Hold'}
              </div>
            )}
          </div>

          {/* Adjacent Clean Batch (Negative Control) */}
          <div
            style={{
              background: 'rgba(16, 185, 129, 0.08)',
              border: '1px solid rgba(16, 185, 129, 0.3)',
              borderRadius: '8px',
              padding: '10px',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '3px' }}>
              <span className="badge badge-emerald">Negative Control</span>
              <span style={{ fontSize: '0.72rem', fontFamily: 'var(--font-mono)' }}>100 Qty</span>
            </div>
            <div style={{ fontWeight: 700, fontSize: '0.82rem', fontFamily: 'var(--font-mono)' }}>
              FP-100-ADJ (ING-4418)
            </div>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', marginTop: '2px' }}>
              Clean Silo 2 flour.
            </div>
            <div style={{ marginTop: '6px', fontSize: '0.7rem', color: 'var(--accent-emerald)', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <ShieldCheck size={12} /> 0 Held · Verified Clear
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
