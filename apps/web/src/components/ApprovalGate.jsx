import React, { useState, useEffect } from 'react';
import {
  UserCheck,
  Send,
  Lock,
  CheckCircle2,
  Clock,
  PhoneCall,
  ShieldCheck,
  FileCheck,
  X,
} from 'lucide-react';

export function ApprovalGate({
  phase,
  onApproveContainment,
  onDispatchOutbox,
  onRequestClosure,
  onResolveAck,
  onReleaseHold,
  onCloseWithNonResponse,
  onTtlExpired,
  onExtendTtl,
  loading,
  approvals,
  closureGate,
}) {
  const [rationale, setRationale] = useState(
    'Authorized containment under policy EVAL-HOLD-01 based on positive lab Salmonella finding.'
  );
  const [secondsRemaining, setSecondsRemaining] = useState(1800); // 30 mins
  const [isPhoneModalOpen, setIsPhoneModalOpen] = useState(false);
  const [isReleaseModalOpen, setIsReleaseModalOpen] = useState(false);
  const [isNonResponseModalOpen, setIsNonResponseModalOpen] = useState(false);

  // Phone Attestation Form State
  const [callerId, setCallerId] = useState('OPS-001 (Sarah Jenkins, Customer Operations)');
  const [recipientContact, setRecipientContact] = useState('David Miller (Receiving Lead, Midwest Wholesale Dist-06)');
  const [recipientPhone, setRecipientPhone] = useState('+1 (612) 555-0194');
  const [attestationNotes, setAttestationNotes] = useState(
    'Spoke directly with David Miller. Confirmed receipt of Urgent Recall Notice PKT-001. All 40 units in transit quarantined at dock awaiting return.'
  );

  // Dual-Signature Release Form State
  const [retestDocId, setRetestDocId] = useState('LAB-RETEST-SPL-99824-B');
  const [retestDocHash, setRetestDocHash] = useState('e4b8c719a89d443210feeb89012356789abcdef0123456789abcdef012345678');
  const [qaSignature, setQaSignature] = useState('Dr. Elena Rostova (QA-LEAD-01)');
  const [qaRationale, setQaRationale] = useState('Lab re-test SPL-99824-B satisfies negative culture release criterion under FDA BAM Ch. 5.');
  const [coordSignature, setCoordSignature] = useState('Marcus Vance (RECALL-COORD-01)');
  const [coordRationale, setCoordRationale] = useState('Confirmed re-test documentation attached and validated with lab director. Authorizing inventory release.');

  // Non-Response 21 CFR § 7.49 Form State
  const [regFilingId, setRegFilingId] = useState('FDA-NONRESP-2026-0814-06');
  const [attemptCount, setAttemptCount] = useState(3);
  const [goodFaithNotes, setGoodFaithNotes] = useState(
    '3 documented phone/certified mail outreach attempts without response. Escalated to FDA District Office pursuant to 21 CFR § 7.49.'
  );

  const isQaApproved = approvals?.some((a) => a.decision === 'approved' && a.approval_type === 'containment');
  const isOutboxDispatched = ['ack_monitoring', 'effectiveness_check', 'closed'].includes(phase);
  const isAckResolved = !closureGate?.is_blocked && isOutboxDispatched;
  const isClosed = phase === 'closed';

  // 30-minute countdown with automatic escalation on expiry
  useEffect(() => {
    if (isQaApproved || isClosed) return;
    const interval = setInterval(() => {
      setSecondsRemaining((prev) => {
        if (prev <= 1) {
          clearInterval(interval);
          if (onTtlExpired) onTtlExpired();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(interval);
  }, [isQaApproved, isClosed, onTtlExpired]);

  const formatTimer = (s) => {
    const mins = Math.floor(s / 60);
    const secs = s % 60;
    return `${mins}:${secs < 10 ? '0' : ''}${secs}`;
  };

  const handlePhoneSubmit = (e) => {
    e.preventDefault();
    onResolveAck({
      caller_id: callerId,
      recipient_contact: recipientContact,
      recipient_phone: recipientPhone,
      call_timestamp: new Date().toISOString(),
      attestation_notes: attestationNotes,
    });
    setIsPhoneModalOpen(false);
  };

  const handleReleaseSubmit = (e) => {
    e.preventDefault();
    onReleaseHold({
      retest_doc_id: retestDocId,
      retest_doc_hash: retestDocHash,
      qa_signature: qaSignature,
      qa_rationale: qaRationale,
      coordinator_signature: coordSignature,
      coordinator_rationale: coordRationale,
    });
    setIsReleaseModalOpen(false);
  };

  const handleNonResponseSubmit = (e) => {
    e.preventDefault();
    onCloseWithNonResponse({
      regulatory_filing_id: regFilingId,
      attempt_count: attemptCount,
      good_faith_notes: goodFaithNotes,
    });
    setIsNonResponseModalOpen(false);
  };

  return (
    <div className="card-panel" style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <div className="section-label" style={{ marginBottom: '2px' }}>Governance & Authorization</div>
          <h2 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <UserCheck size={15} style={{ color: 'var(--accent-primary)' }} />
            Human decision gates (Separation of Duties)
          </h2>
        </div>

        <div>
          {isQaApproved ? (
            <span className="status-tag status-tag-success">
              <span className="status-dot status-dot-success" />
              AUTH-HOLD-01 (Firm Quarantine)
            </span>
          ) : (
            <span
              className="status-tag status-tag-warning"
              title="Provisional soft hold active. Click to extend +15m."
              style={{ cursor: 'pointer' }}
              onClick={onExtendTtl}
            >
              <Clock size={12} />
              <span className="mono-val">TTL: {formatTimer(secondsRemaining)} (+15m)</span>
            </span>
          )}
        </div>
      </div>

      {/* Rationale Input */}
      <div>
        <label className="section-label" style={{ display: 'block', marginBottom: '4px' }}>
          Approval Rationale (Immutably appended to audit stream)
        </label>
        <textarea
          value={rationale}
          onChange={(e) => setRationale(e.target.value)}
          rows={2}
          disabled={isClosed}
          style={{
            width: '100%',
            resize: 'vertical',
            fontSize: '12px',
            lineHeight: '1.4',
          }}
          placeholder="Enter operational rationale..."
        />
      </div>

      {/* Decision Actions Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '8px' }}>
        {/* Gate 1: QA Containment Approval */}
        <button
          className={`btn ${!isQaApproved && !isClosed ? 'btn-primary' : 'btn-secondary'}`}
          onClick={() => onApproveContainment(rationale)}
          disabled={loading || isQaApproved || isClosed}
          title="QA Lead sign-off: converts provisional 30m soft hold into authorized firm quarantine"
        >
          <Lock size={13} />
          {isQaApproved ? 'Containment Approved' : 'Approve Firm Quarantine (QA)'}
        </button>

        {/* Gate 2: Dispatch Outbox */}
        <button
          className="btn btn-secondary"
          onClick={onDispatchOutbox}
          disabled={loading || !isQaApproved || isOutboxDispatched || isClosed}
          title="Customer Operations sign-off: dispatch formal recall notices to all 6 consignees"
        >
          <Send size={13} />
          {isOutboxDispatched ? 'Outbox Dispatched' : 'Dispatch Recall Outbox (Ops)'}
        </button>

        {/* Gate 3: Resolve ACK-006 via Phone */}
        <button
          className="btn btn-secondary"
          onClick={() => setIsPhoneModalOpen(true)}
          disabled={loading || !isOutboxDispatched || isAckResolved || isClosed}
          title="Record signed phone attestation verifying distributor ACK-006 receipt"
        >
          <PhoneCall size={13} />
          {isAckResolved ? 'ACK-006 Resolved' : 'Verify Phone Attestation'}
        </button>

        {/* Gate 4: Dual-Signature Release Rail */}
        <button
          className="btn btn-secondary"
          onClick={() => setIsReleaseModalOpen(true)}
          disabled={loading || !isQaApproved || isClosed}
          title="Execute dual-signature inventory release with negative re-test biological proof"
        >
          <FileCheck size={13} />
          Dual-Signature Release Rail
        </button>

        {/* Gate 5: Non-Response Closure (21 CFR § 7.49) */}
        <button
          className="btn btn-secondary"
          onClick={() => setIsNonResponseModalOpen(true)}
          disabled={loading || !isOutboxDispatched || isClosed}
          title="Document certified non-response under 21 CFR § 7.49 and refer to FDA District Office"
        >
          <ShieldCheck size={13} />
          Non-Response Close (§ 7.49)
        </button>

        {/* Gate 6: Request Closure */}
        <button
          className={`btn ${isClosed ? 'btn-secondary' : 'btn-ghost'}`}
          onClick={onRequestClosure}
          disabled={loading || isClosed}
          title={
            closureGate?.is_blocked
              ? 'Closure blocked: Unverified consignee acknowledgements remain.'
              : 'Submit for case closure disposition'
          }
        >
          <CheckCircle2 size={13} />
          {isClosed ? 'Case Closed & Archived' : 'Request Case Closure'}
        </button>
      </div>

      {/* MODAL 1: Phone Attestation Modal */}
      {isPhoneModalOpen && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            width: '100vw',
            height: '100vh',
            background: 'rgba(0, 0, 0, 0.75)',
            zIndex: 100,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '20px',
          }}
          onClick={() => setIsPhoneModalOpen(false)}
        >
          <div
            className="card-panel"
            style={{
              maxWidth: '520px',
              width: '100%',
              background: 'var(--bg-surface)',
              border: '1px solid var(--border-medium)',
              padding: '20px',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <PhoneCall size={16} style={{ color: 'var(--accent-primary)' }} />
                <h3 style={{ fontSize: '14px', fontWeight: 600 }}>Phone Attestation Record (ACK-006)</h3>
              </div>
              <button className="btn btn-ghost" style={{ padding: '4px' }} onClick={() => setIsPhoneModalOpen(false)}>
                <X size={16} />
              </button>
            </div>

            <form onSubmit={handlePhoneSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '10px', fontSize: '12px' }}>
              <div>
                <label className="section-label" style={{ display: 'block', marginBottom: '2px' }}>Caller Identifier</label>
                <input
                  type="text"
                  value={callerId}
                  onChange={(e) => setCallerId(e.target.value)}
                  style={{ width: '100%' }}
                  required
                />
              </div>

              <div>
                <label className="section-label" style={{ display: 'block', marginBottom: '2px' }}>Recipient Contact</label>
                <input
                  type="text"
                  value={recipientContact}
                  onChange={(e) => setRecipientContact(e.target.value)}
                  style={{ width: '100%' }}
                  required
                />
              </div>

              <div>
                <label className="section-label" style={{ display: 'block', marginBottom: '2px' }}>Phone Number & Timestamp</label>
                <input
                  type="text"
                  value={recipientPhone}
                  onChange={(e) => setRecipientPhone(e.target.value)}
                  style={{ width: '100%' }}
                  required
                />
              </div>

              <div>
                <label className="section-label" style={{ display: 'block', marginBottom: '2px' }}>Attestation Notes</label>
                <textarea
                  value={attestationNotes}
                  onChange={(e) => setAttestationNotes(e.target.value)}
                  rows={3}
                  style={{ width: '100%' }}
                  required
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '10px' }}>
                <button type="button" className="btn btn-ghost" onClick={() => setIsPhoneModalOpen(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary">
                  Sign & Record Attestation
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL 2: Dual-Signature Release Rail Modal */}
      {isReleaseModalOpen && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            width: '100vw',
            height: '100vh',
            background: 'rgba(0, 0, 0, 0.75)',
            zIndex: 100,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '20px',
          }}
          onClick={() => setIsReleaseModalOpen(false)}
        >
          <div
            className="card-panel"
            style={{
              maxWidth: '560px',
              width: '100%',
              background: 'var(--bg-surface)',
              border: '1px solid var(--border-medium)',
              padding: '20px',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <FileCheck size={16} style={{ color: 'var(--accent-primary)' }} />
                <h3 style={{ fontSize: '14px', fontWeight: 600 }}>Dual-Signature Hold Release Rail</h3>
              </div>
              <button className="btn btn-ghost" style={{ padding: '4px' }} onClick={() => setIsReleaseModalOpen(false)}>
                <X size={16} />
              </button>
            </div>

            <form onSubmit={handleReleaseSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '10px', fontSize: '12px' }}>
              <div style={{ background: 'var(--bg-surface-subtle)', padding: '8px 10px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)', fontSize: '11px', color: 'var(--text-muted)' }}>
                Step 1: QA Lead biological clearance → Step 2: Closure Authority inventory release.
              </div>

              <div>
                <label className="section-label" style={{ display: 'block', marginBottom: '2px' }}>Lab Re-test Document ID</label>
                <input
                  type="text"
                  value={retestDocId}
                  onChange={(e) => setRetestDocId(e.target.value)}
                  style={{ width: '100%' }}
                  required
                />
              </div>

              <div>
                <label className="section-label" style={{ display: 'block', marginBottom: '2px' }}>Re-test SHA-256 Digest</label>
                <input
                  type="text"
                  value={retestDocHash}
                  onChange={(e) => setRetestDocHash(e.target.value)}
                  className="mono-val"
                  style={{ width: '100%', fontSize: '11px' }}
                  required
                />
              </div>

              <div>
                <label className="section-label" style={{ display: 'block', marginBottom: '2px' }}>QA Clearance Rationale</label>
                <input
                  type="text"
                  value={qaRationale}
                  onChange={(e) => setQaRationale(e.target.value)}
                  style={{ width: '100%' }}
                  required
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '10px' }}>
                <button type="button" className="btn btn-ghost" onClick={() => setIsReleaseModalOpen(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary">
                  Sign & Authorize Release
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL 3: Non-Response 21 CFR § 7.49 Modal */}
      {isNonResponseModalOpen && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            width: '100vw',
            height: '100vh',
            background: 'rgba(0, 0, 0, 0.75)',
            zIndex: 100,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '20px',
          }}
          onClick={() => setIsNonResponseModalOpen(false)}
        >
          <div
            className="card-panel"
            style={{
              maxWidth: '520px',
              width: '100%',
              background: 'var(--bg-surface)',
              border: '1px solid var(--border-medium)',
              padding: '20px',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <ShieldCheck size={16} style={{ color: 'var(--accent-primary)' }} />
                <h3 style={{ fontSize: '14px', fontWeight: 600 }}>21 CFR § 7.49 Non-Response Closure</h3>
              </div>
              <button className="btn btn-ghost" style={{ padding: '4px' }} onClick={() => setIsNonResponseModalOpen(false)}>
                <X size={16} />
              </button>
            </div>

            <form onSubmit={handleNonResponseSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '10px', fontSize: '12px' }}>
              <div>
                <label className="section-label" style={{ display: 'block', marginBottom: '2px' }}>FDA Regulatory Filing ID</label>
                <input
                  type="text"
                  value={regFilingId}
                  onChange={(e) => setRegFilingId(e.target.value)}
                  style={{ width: '100%' }}
                  required
                />
              </div>

              <div>
                <label className="section-label" style={{ display: 'block', marginBottom: '2px' }}>Documented Attempt Count (Minimum 3)</label>
                <input
                  type="number"
                  min={3}
                  value={attemptCount}
                  onChange={(e) => setAttemptCount(parseInt(e.target.value) || 3)}
                  style={{ width: '100%' }}
                  required
                />
              </div>

              <div>
                <label className="section-label" style={{ display: 'block', marginBottom: '2px' }}>Good-Faith Legal Certification Notes</label>
                <textarea
                  value={goodFaithNotes}
                  onChange={(e) => setGoodFaithNotes(e.target.value)}
                  rows={3}
                  style={{ width: '100%' }}
                  required
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '10px' }}>
                <button type="button" className="btn btn-ghost" onClick={() => setIsNonResponseModalOpen(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary">
                  Certify & Close Under § 7.49
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
