import React from 'react';
import { Hash, CheckCircle2, AlertCircle, ShieldCheck, PhoneCall, UserCheck } from 'lucide-react';

export function EvidenceLedger({
  acknowledgements,
  closureGate,
  ledgerCount,
  approvals,
  phase,
  attestationData,
}) {
  const acks = acknowledgements || [];
  const isBlocked = closureGate?.is_blocked;
  const isClosed = phase === 'closed';

  return (
    <div className="card-panel" style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <div className="section-label" style={{ marginBottom: '2px' }}>Audit Stream</div>
          <h2 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Hash size={15} style={{ color: 'var(--accent-primary)' }} />
            Evidence ledger & audit trail
          </h2>
        </div>
        <span className="status-tag mono-val">
          {ledgerCount || 0} Ledger Events
        </span>
      </div>

      {/* Dynamic Disposition Banner */}
      <div
        style={{
          background: isClosed
            ? 'var(--status-success-subtle)'
            : (isBlocked ? 'var(--status-danger-subtle)' : 'var(--bg-surface-subtle)'),
          border: `1px solid ${
            isClosed
              ? 'rgba(34, 197, 94, 0.3)'
              : (isBlocked ? 'rgba(239, 68, 68, 0.3)' : 'var(--border-subtle)')
          }`,
          borderRadius: 'var(--radius-md)',
          padding: '10px 12px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '3px' }}>
          <span
            className={`status-dot ${
              isClosed ? 'status-dot-success' : (isBlocked ? 'status-dot-danger' : 'status-dot-neutral')
            }`}
          />
          <span
            style={{
              fontWeight: 600,
              fontSize: '12px',
              color: isClosed
                ? 'var(--status-success-text)'
                : (isBlocked ? 'var(--status-danger-text)' : 'var(--text-primary)'),
            }}
          >
            {isClosed
              ? 'Incident Disposition Complete'
              : isBlocked
              ? 'Closure Blocked: Outstanding ACK-006'
              : 'Evaluation Case Active'}
          </span>
        </div>
        <p style={{ fontSize: '11px', color: 'var(--text-secondary)', lineHeight: '1.4' }}>
          {isClosed
            ? 'Evidence reconciliation finalized. Full tamper-evident audit record archived under 21 CFR regulations.'
            : isBlocked
            ? 'Autonomous closure strictly refused: Distributor ACK-006 has not verified receipt. Use "Verify Phone Attestation" or "Non-Response Close" to proceed.'
            : 'Operational containment and consignee tracking in progress.'}
        </p>
      </div>

      {/* Human Signed Approvals Audit */}
      {approvals && approvals.length > 0 && (
        <div
          style={{
            background: 'var(--bg-surface-subtle)',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--border-subtle)',
            padding: '10px 12px',
            fontSize: '12px',
            display: 'flex',
            flexDirection: 'column',
            gap: '6px',
          }}
        >
          <div className="section-label" style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <UserCheck size={12} /> Verified Audit Signatures (ISO 8601)
          </div>
          {approvals.map((app) => (
            <div key={app.approval_id} style={{ borderBottom: '1px solid var(--border-subtle)', paddingBottom: '4px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-primary)' }}>
                <strong>{app.approver_name || app.approver_id}</strong>
                <span className="mono-val" style={{ color: 'var(--text-muted)', fontSize: '11px' }}>
                  {app.decided_at ? new Date(app.decided_at).toISOString().replace('T', ' ').substring(0, 19) : '2026-08-14 12:04:18'}
                </span>
              </div>
              <div style={{ color: 'var(--text-muted)', fontSize: '11px', fontStyle: 'italic', marginTop: '2px' }}>
                "{app.rationale}"
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Signed Phone Attestation Metadata */}
      {attestationData && (
        <div
          style={{
            background: 'var(--bg-surface-subtle)',
            border: '1px solid var(--accent-primary)',
            borderRadius: 'var(--radius-md)',
            padding: '8px 10px',
            fontSize: '11px',
          }}
        >
          <div className="section-label" style={{ color: 'var(--accent-primary)', display: 'flex', alignItems: 'center', gap: '4px', marginBottom: '2px' }}>
            <PhoneCall size={11} /> Signed Phone Attestation Attached
          </div>
          <div style={{ color: 'var(--text-secondary)' }}>Caller: {attestationData.caller_id}</div>
          <div style={{ color: 'var(--text-secondary)' }}>Contact: {attestationData.recipient_contact}</div>
          <div className="mono-val" style={{ color: 'var(--text-muted)', wordBreak: 'break-all', marginTop: '2px', fontSize: '10px' }}>
            Digest: {attestationData.attestation_hash}
          </div>
        </div>
      )}

      {/* Consignee Outreach Outbox */}
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px', fontSize: '11px' }}>
          <span className="section-label">
            Consignee Outbox ({acks.filter((a) => a.status === 'verified').length}/6 Confirmed)
          </span>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          {acks.length === 0 ? (
            <div style={{ fontSize: '12px', color: 'var(--text-muted)', fontStyle: 'italic', padding: '6px 0' }}>
              No notification packet dispatched yet.
            </div>
          ) : (
            acks.map((ack) => {
              const isVerified = ack.status === 'verified';
              return (
                <div
                  key={ack.acknowledgement_id}
                  style={{
                    background: isVerified ? 'var(--status-success-subtle)' : 'var(--status-warning-subtle)',
                    border: `1px solid ${isVerified ? 'rgba(34, 197, 94, 0.2)' : 'rgba(245, 158, 11, 0.3)'}`,
                    borderRadius: 'var(--radius-sm)',
                    padding: '5px 8px',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    fontSize: '11px',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span className={`status-dot ${isVerified ? 'status-dot-success' : 'status-dot-warning'}`} />
                    <span className="mono-val" style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                      {ack.acknowledgement_id}
                    </span>
                    <span style={{ color: 'var(--text-muted)' }}>· {ack.recipient_id}</span>
                  </div>

                  <span className="mono-val" style={{ color: isVerified ? 'var(--status-success-text)' : 'var(--status-warning-text)' }}>
                    {isVerified ? (ack.verified_at ? 'Verified' : 'Signed Attestation') : 'Pending Verification'}
                  </span>
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
