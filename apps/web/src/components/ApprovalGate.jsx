import React, { useState, useEffect } from 'react';
import {
  UserCheck,
  ShieldAlert,
  Send,
  Lock,
  CheckCircle2,
  AlertTriangle,
  Clock,
  PhoneCall,
  RotateCcw,
  ShieldCheck,
  FileCheck,
  PlusCircle,
  FileText,
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

  const isQaApproved = approvals?.some(a => a.decision === 'approved' && a.approval_type === 'containment');
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

  return (
    <div className="glass-panel" style={{ padding: '18px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <UserCheck size={18} color="var(--accent-cyan)" />
          <h2 style={{ fontSize: '1.05rem', fontWeight: 700 }}>Human Decision Gates (Separation of Duties)</h2>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {isQaApproved ? (
            <span className="badge badge-emerald">
              <ShieldCheck size={12} /> AUTH-HOLD-01 (Firm Quarantine)
            </span>
          ) : (
            <span
              className="badge badge-amber"
              title="Provisional soft hold active. Auto-escalates at 00:00."
              style={{ cursor: 'pointer' }}
              onClick={onExtendTtl}
            >
              <Clock size={12} /> TTL: {formatTimer(secondsRemaining)} (+15m)
            </span>
          )}
        </div>
      </div>

      {/* Rationale Input */}
      <div>
        <label
          style={{
            display: 'block',
            fontSize: '0.72rem',
            color: 'var(--text-secondary)',
            marginBottom: '4px',
            fontWeight: 600,
          }}
        >
          MANDATORY APPROVAL RATIONALE (IMMUTABLY LOGGED TO LEDGER):
        </label>
        <textarea
          value={rationale}
          onChange={(e) => setRationale(e.target.value)}
          rows={2}
          disabled={isClosed}
          style={{
            width: '100%',
            background: 'rgba(0, 0, 0, 0.4)',
            border: '1px solid var(--border-subtle)',
            borderRadius: '8px',
            padding: '8px 10px',
            color: 'var(--text-primary)',
            fontSize: '0.78rem',
            fontFamily: 'var(--font-sans)',
            resize: 'none',
          }}
        />
      </div>

      {/* Dual Role Approval Gates */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
        {/* Gate 1: QA Lead */}
        <div
          style={{
            background: 'rgba(0, 0, 0, 0.3)',
            border: isQaApproved ? '1px solid rgba(16, 185, 129, 0.3)' : '1px solid var(--border-subtle)',
            borderRadius: '8px',
            padding: '10px',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
            gap: '8px',
          }}
        >
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: '0.72rem', color: 'var(--accent-cyan)', fontWeight: 700 }}>
                ROLE 1: QA LEAD
              </span>
              {isQaApproved && <CheckCircle2 size={14} color="var(--accent-emerald)" />}
            </div>
            <div style={{ fontSize: '0.8rem', fontWeight: 700, color: '#f8fafc' }}>
              Dr. Elena Rostova (QA-LEAD-01)
            </div>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
              Validates biology & locks firm quarantine policy.
            </div>
          </div>

          <button
            className={`btn-kinetic ${isQaApproved ? 'btn-emerald' : 'btn-primary'}`}
            onClick={() => onApproveContainment(rationale)}
            disabled={loading || isQaApproved || isClosed}
            style={{ width: '100%', padding: '8px 12px', fontSize: '0.78rem' }}
          >
            {isQaApproved ? (
              <>
                <CheckCircle2 size={14} /> Signed: Firm Quarantine
              </>
            ) : (
              <>
                <ShieldAlert size={14} /> Sign Biological Containment
              </>
            )}
          </button>
        </div>

        {/* Gate 2: Recall Coordinator */}
        <div
          style={{
            background: 'rgba(0, 0, 0, 0.3)',
            border: isOutboxDispatched ? '1px solid rgba(16, 185, 129, 0.3)' : '1px solid var(--border-subtle)',
            borderRadius: '8px',
            padding: '10px',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
            gap: '8px',
          }}
        >
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: '0.72rem', color: 'var(--accent-cyan)', fontWeight: 700 }}>
                ROLE 2: RECALL COORDINATOR
              </span>
              {isOutboxDispatched && <CheckCircle2 size={14} color="var(--accent-emerald)" />}
            </div>
            <div style={{ fontSize: '0.8rem', fontWeight: 700, color: '#f8fafc' }}>
              Marcus Vance (RECALL-COORD-01)
            </div>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
              Authorizes consignee packet & monitors distributor outreach.
            </div>
          </div>

          <button
            className={`btn-kinetic ${isOutboxDispatched ? 'btn-emerald' : 'btn-primary'}`}
            onClick={onDispatchOutbox}
            disabled={loading || !isQaApproved || isOutboxDispatched || isClosed}
            style={{ width: '100%', padding: '8px 12px', fontSize: '0.78rem' }}
          >
            {isOutboxDispatched ? (
              <>
                <CheckCircle2 size={14} /> Outbox Dispatched (6/6)
              </>
            ) : (
              <>
                <Send size={14} /> Authorize & Send Outbox
              </>
            )}
          </button>
        </div>
      </div>

      {/* Operational Actions Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '6px', marginTop: '2px' }}>
        {/* Action 1: Signed Phone Attestation Modal Trigger */}
        <button
          className={`btn-kinetic ${isAckResolved ? 'btn-emerald' : 'btn-secondary'}`}
          onClick={() => setIsPhoneModalOpen(true)}
          disabled={loading || !isOutboxDispatched || isAckResolved || isClosed}
          style={{ padding: '7px 8px', fontSize: '0.72rem' }}
          title="Attach signed call attestation with caller ID, contact person, and notes"
        >
          <PhoneCall size={13} />
          {isAckResolved ? 'ACK-006 Signed' : 'Sign Phone Attest'}
        </button>

        {/* Action 2: Audit & Close Case */}
        <button
          className={`btn-kinetic ${isClosed ? 'btn-emerald' : 'btn-secondary'}`}
          onClick={onRequestClosure}
          disabled={loading || !isOutboxDispatched || isClosed}
          style={{
            padding: '7px 8px',
            fontSize: '0.72rem',
            borderColor: isClosed ? 'var(--accent-emerald)' : 'var(--border-danger)',
            color: isClosed ? 'var(--accent-emerald)' : 'var(--accent-amber)',
          }}
          title="Attempt formal incident closure"
        >
          <Lock size={13} />
          {isClosed ? 'Case Closed' : 'Audit & Close'}
        </button>

        {/* Action 3: Documented Non-Response Closure (21 CFR § 7.49) */}
        <button
          className="btn-kinetic btn-secondary"
          onClick={() => setIsNonResponseModalOpen(true)}
          disabled={loading || !isOutboxDispatched || isClosed || isAckResolved}
          style={{ padding: '7px 8px', fontSize: '0.72rem', color: 'var(--accent-amber)' }}
          title="Close with certified 3-attempt non-response and FDA District Office referral"
        >
          <FileCheck size={13} />
          Non-Response Close
        </button>

        {/* Action 4: Symmetrical Dual-Signature Release Modal Trigger */}
        <button
          className="btn-kinetic btn-secondary"
          onClick={() => setIsReleaseModalOpen(true)}
          disabled={loading || isClosed}
          style={{ padding: '7px 8px', fontSize: '0.72rem', color: 'var(--text-secondary)' }}
          title="Authorize inventory un-hold requiring lab re-test hash and dual QA + Coordinator signatures"
        >
          <RotateCcw size={13} />
          Dual Release
        </button>
      </div>

      {/* Modal 1: Signed Phone Attestation */}
      {isPhoneModalOpen && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            width: '100vw',
            height: '100vh',
            background: 'rgba(0, 0, 0, 0.8)',
            zIndex: 150,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '20px',
          }}
        >
          <div className="glass-panel" style={{ maxWidth: '520px', width: '100%', padding: '22px' }}>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 800, marginBottom: '6px', color: 'var(--accent-cyan)' }}>
              Signed Phone Verification Attestation (ACK-006)
            </h3>
            <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginBottom: '14px' }}>
              FDA compliance requires full operator identity, contact person, timestamp, and free-text notes before verifying oral receipt.
            </p>
            <form onSubmit={handlePhoneSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '10px', fontSize: '0.78rem' }}>
              <div>
                <label style={{ display: 'block', color: 'var(--text-muted)', marginBottom: '2px' }}>CALLER IDENTITY (CUSTOMER OPS):</label>
                <input
                  type="text"
                  value={callerId}
                  onChange={(e) => setCallerId(e.target.value)}
                  style={{ width: '100%', padding: '6px 10px', background: 'rgba(0,0,0,0.5)', border: '1px solid var(--border-subtle)', borderRadius: '6px', color: '#fff' }}
                  required
                />
              </div>
              <div>
                <label style={{ display: 'block', color: 'var(--text-muted)', marginBottom: '2px' }}>RECIPIENT CONTACT NAME & ROLE:</label>
                <input
                  type="text"
                  value={recipientContact}
                  onChange={(e) => setRecipientContact(e.target.value)}
                  style={{ width: '100%', padding: '6px 10px', background: 'rgba(0,0,0,0.5)', border: '1px solid var(--border-subtle)', borderRadius: '6px', color: '#fff' }}
                  required
                />
              </div>
              <div>
                <label style={{ display: 'block', color: 'var(--text-muted)', marginBottom: '2px' }}>PHONE NUMBER DIALED:</label>
                <input
                  type="text"
                  value={recipientPhone}
                  onChange={(e) => setRecipientPhone(e.target.value)}
                  style={{ width: '100%', padding: '6px 10px', background: 'rgba(0,0,0,0.5)', border: '1px solid var(--border-subtle)', borderRadius: '6px', color: '#fff' }}
                  required
                />
              </div>
              <div>
                <label style={{ display: 'block', color: 'var(--text-muted)', marginBottom: '2px' }}>MANDATORY ATTESTATION RECORD / CALL NOTES:</label>
                <textarea
                  value={attestationNotes}
                  onChange={(e) => setAttestationNotes(e.target.value)}
                  rows={3}
                  style={{ width: '100%', padding: '6px 10px', background: 'rgba(0,0,0,0.5)', border: '1px solid var(--border-subtle)', borderRadius: '6px', color: '#fff', resize: 'none' }}
                  required
                />
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '10px' }}>
                <button type="button" className="btn-kinetic btn-secondary" onClick={() => setIsPhoneModalOpen(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn-kinetic btn-primary">
                  Sign & Attach SHA-256 Digest
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal 2: Symmetrical Dual-Signature Release */}
      {isReleaseModalOpen && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            width: '100vw',
            height: '100vh',
            background: 'rgba(0, 0, 0, 0.8)',
            zIndex: 150,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '20px',
          }}
        >
          <div className="glass-panel" style={{ maxWidth: '600px', width: '100%', padding: '22px' }}>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 800, marginBottom: '4px', color: 'var(--accent-emerald)' }}>
              Dual-Signature Inventory Release Authorization
            </h3>
            <p style={{ fontSize: '0.74rem', color: 'var(--text-secondary)', marginBottom: '12px' }}>
              Releasing product into commerce requires negative lab re-test documentation hash AND symmetrical signatures from both QA Lead and Recall Coordinator.
            </p>
            <form onSubmit={handleReleaseSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '0.76rem' }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                <div>
                  <label style={{ display: 'block', color: 'var(--text-muted)' }}>RE-TEST DOC ID:</label>
                  <input
                    type="text"
                    value={retestDocId}
                    onChange={(e) => setRetestDocId(e.target.value)}
                    style={{ width: '100%', padding: '5px 8px', background: 'rgba(0,0,0,0.5)', border: '1px solid var(--border-subtle)', borderRadius: '6px', color: '#fff' }}
                    required
                  />
                </div>
                <div>
                  <label style={{ display: 'block', color: 'var(--text-muted)' }}>RE-TEST LAB SHA-256 HASH:</label>
                  <input
                    type="text"
                    value={retestDocHash}
                    onChange={(e) => setRetestDocHash(e.target.value)}
                    style={{ width: '100%', padding: '5px 8px', background: 'rgba(0,0,0,0.5)', border: '1px solid var(--border-subtle)', borderRadius: '6px', color: '#fff' }}
                    required
                  />
                </div>
              </div>
              <div>
                <label style={{ display: 'block', color: 'var(--text-muted)' }}>QA LEAD SIGNATURE (Dr. Elena Rostova):</label>
                <input
                  type="text"
                  value={qaSignature}
                  onChange={(e) => setQaSignature(e.target.value)}
                  style={{ width: '100%', padding: '5px 8px', background: 'rgba(0,0,0,0.5)', border: '1px solid var(--border-subtle)', borderRadius: '6px', color: '#fff' }}
                  required
                />
              </div>
              <div>
                <label style={{ display: 'block', color: 'var(--text-muted)' }}>QA BIOLOGICAL RATIONALE:</label>
                <input
                  type="text"
                  value={qaRationale}
                  onChange={(e) => setQaRationale(e.target.value)}
                  style={{ width: '100%', padding: '5px 8px', background: 'rgba(0,0,0,0.5)', border: '1px solid var(--border-subtle)', borderRadius: '6px', color: '#fff' }}
                  required
                />
              </div>
              <div>
                <label style={{ display: 'block', color: 'var(--text-muted)' }}>RECALL COORDINATOR SIGNATURE (Marcus Vance):</label>
                <input
                  type="text"
                  value={coordSignature}
                  onChange={(e) => setCoordSignature(e.target.value)}
                  style={{ width: '100%', padding: '5px 8px', background: 'rgba(0,0,0,0.5)', border: '1px solid var(--border-subtle)', borderRadius: '6px', color: '#fff' }}
                  required
                />
              </div>
              <div>
                <label style={{ display: 'block', color: 'var(--text-muted)' }}>OPERATIONAL CLEARANCE RATIONALE:</label>
                <input
                  type="text"
                  value={coordRationale}
                  onChange={(e) => setCoordRationale(e.target.value)}
                  style={{ width: '100%', padding: '5px 8px', background: 'rgba(0,0,0,0.5)', border: '1px solid var(--border-subtle)', borderRadius: '6px', color: '#fff' }}
                  required
                />
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '10px' }}>
                <button type="button" className="btn-kinetic btn-secondary" onClick={() => setIsReleaseModalOpen(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn-kinetic btn-emerald">
                  Authorize Dual Release & Clear Hold
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal 3: Documented Non-Response Closure */}
      {isNonResponseModalOpen && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            width: '100vw',
            height: '100vh',
            background: 'rgba(0, 0, 0, 0.8)',
            zIndex: 150,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '20px',
          }}
        >
          <div className="glass-panel" style={{ maxWidth: '520px', width: '100%', padding: '22px' }}>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 800, marginBottom: '4px', color: 'var(--accent-amber)' }}>
              Certified Good-Faith Closure (21 CFR § 7.49)
            </h3>
            <p style={{ fontSize: '0.74rem', color: 'var(--text-secondary)', marginBottom: '12px' }}>
              When a consignee is non-responsive after repeated documented attempts, regulatory guidelines permit case closure with certified district office referral.
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '0.76rem' }}>
              <div>
                <label style={{ display: 'block', color: 'var(--text-muted)' }}>REGULATORY FILING NUMBER:</label>
                <input
                  type="text"
                  defaultValue="FDA-DISTRICT-ESCALATION-2026-08-01"
                  readOnly
                  style={{ width: '100%', padding: '5px 8px', background: 'rgba(0,0,0,0.5)', border: '1px solid var(--border-subtle)', borderRadius: '6px', color: '#fff' }}
                />
              </div>
              <div>
                <label style={{ display: 'block', color: 'var(--text-muted)' }}>VERIFIED CONTACT ATTEMPTS:</label>
                <input
                  type="text"
                  defaultValue="3 attempts (Phone, Certified Email, Courier Delivery)"
                  readOnly
                  style={{ width: '100%', padding: '5px 8px', background: 'rgba(0,0,0,0.5)', border: '1px solid var(--border-subtle)', borderRadius: '6px', color: '#fff' }}
                />
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '10px' }}>
                <button type="button" className="btn-kinetic btn-secondary" onClick={() => setIsNonResponseModalOpen(false)}>
                  Cancel
                </button>
                <button
                  type="button"
                  className="btn-kinetic btn-primary"
                  onClick={() => {
                    onCloseWithNonResponse();
                    setIsNonResponseModalOpen(false);
                  }}
                >
                  Certify Good-Faith & Close Case
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
