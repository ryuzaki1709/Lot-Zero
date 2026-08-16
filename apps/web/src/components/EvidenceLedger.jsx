import React from 'react';

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
  const verifiedCount = acks.filter((a) => a.status === 'verified').length;

  return (
    <section className="section">
      <div className="section-head">
        <div>
          <h2 className="section-title">Audit trail</h2>
          <p className="section-desc">
            Signed approvals, consignee acknowledgements, and the hash-chained event ledger backing
            this incident.
          </p>
        </div>
        {ledgerCount !== undefined && ledgerCount !== null && (
          <span style={{ fontSize: '13px', color: 'var(--text-muted)', fontVariantNumeric: 'tabular-nums' }}>
            {ledgerCount} ledger events
          </span>
        )}
      </div>

      {/* Disposition line */}
      <div
        className="status-inline"
        style={{
          fontSize: '14px',
          marginBottom: '24px',
          color: isClosed
            ? 'var(--status-success-text)'
            : isBlocked
            ? 'var(--status-danger-text)'
            : 'var(--text-secondary)',
        }}
      >
        <span
          className={`status-dot ${
            isClosed ? 'status-dot-success' : isBlocked ? 'status-dot-danger' : 'status-dot-neutral'
          }`}
        />
        {isClosed
          ? 'Incident disposition complete — tamper-evident audit record archived under 21 CFR.'
          : isBlocked
          ? `Closure blocked — ${
              (closureGate?.outstanding_acknowledgements || []).join(', ') || 'consignee acknowledgements'
            } unverified. Resolve by phone attestation or non-response filing.`
          : 'Incident case active — containment and consignee tracking in progress.'}
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {/* Signed approvals */}
        <div className="card-panel">
          <h3 style={{ fontSize: '15px', fontWeight: 600, marginBottom: '6px' }}>Signed approvals</h3>
          {!approvals || approvals.length === 0 ? (
            <p style={{ fontSize: '13.5px', color: 'var(--text-muted)' }}>No approvals recorded yet.</p>
          ) : (
            <div>
              {approvals.map((app, i) => (
                <div
                  key={app.approval_id || i}
                  style={{
                    padding: '14px 0',
                    borderBottom: i < approvals.length - 1 ? '1px solid var(--border-subtle)' : 'none',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap' }}>
                    <span style={{ fontWeight: 600, fontSize: '14px' }}>
                      {app.approver_name || app.approver_id}
                    </span>
                    <span className="mono-val" style={{ color: 'var(--text-muted)', fontSize: '12px' }}>
                      {app.decided_at
                        ? new Date(app.decided_at).toISOString().replace('T', ' ').substring(0, 19)
                        : '-'}
                    </span>
                  </div>
                  <p style={{ color: 'var(--text-secondary)', fontSize: '13px', fontStyle: 'italic', marginTop: '4px' }}>
                    “{app.rationale}”
                  </p>
                </div>
              ))}
            </div>
          )}

          {attestationData && (
            <div style={{ marginTop: '16px', paddingTop: '16px', borderTop: '1px solid var(--border-subtle)', fontSize: '13px' }}>
              <div style={{ fontWeight: 600, marginBottom: '6px', color: 'var(--accent-primary)' }}>
                Signed phone attestation attached
              </div>
              <div style={{ color: 'var(--text-secondary)' }}>Caller — {attestationData.caller_id}</div>
              <div style={{ color: 'var(--text-secondary)' }}>Contact — {attestationData.recipient_contact}</div>
              <div className="mono-val" style={{ color: 'var(--text-muted)', wordBreak: 'break-all', marginTop: '6px', fontSize: '11.5px' }}>
                {attestationData.attestation_hash}
              </div>
            </div>
          )}
        </div>

        {/* Consignee outbox */}
        <div className="card-panel">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: '6px' }}>
            <h3 style={{ fontSize: '15px', fontWeight: 600 }}>Consignee outbox</h3>
            {acks.length > 0 && (
              <span style={{ fontSize: '13px', color: 'var(--text-muted)', fontVariantNumeric: 'tabular-nums' }}>
                {verifiedCount} of {acks.length} confirmed
              </span>
            )}
          </div>

          {acks.length === 0 ? (
            <p style={{ fontSize: '13.5px', color: 'var(--text-muted)' }}>No notification packet dispatched yet.</p>
          ) : (
            <div>
              {acks.map((ack, i) => {
                const isVerified = ack.status === 'verified';
                return (
                  <div
                    key={ack.acknowledgement_id}
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      gap: '12px',
                      padding: '11px 0',
                      borderBottom: i < acks.length - 1 ? '1px solid var(--border-subtle)' : 'none',
                      fontSize: '13.5px',
                    }}
                  >
                    <span className="status-inline" style={{ minWidth: 0 }}>
                      <span className={`status-dot ${isVerified ? 'status-dot-success' : 'status-dot-warning'}`} />
                      <span className="mono-val" style={{ fontWeight: 500, color: 'var(--text-primary)' }}>
                        {ack.acknowledgement_id}
                      </span>
                      <span style={{ color: 'var(--text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {ack.recipient_id}
                      </span>
                    </span>
                    <span style={{ color: isVerified ? 'var(--status-success-text)' : 'var(--status-warning-text)', whiteSpace: 'nowrap' }}>
                      {isVerified ? (ack.attestation_hash ? 'Phone attestation' : 'Verified') : 'Pending'}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
