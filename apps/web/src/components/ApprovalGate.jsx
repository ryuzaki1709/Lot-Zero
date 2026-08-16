import React, { useState, useEffect, useRef } from 'react';
import {
  UserCheck,
  Send,
  Lock,
  CheckCircle2,
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
  loading,
  approvals,
  closureGate,
  containmentActions = [],
}) {
  const [rationale, setRationale] = useState(
    'Authorized containment under policy EVAL-HOLD-01 based on positive lab Salmonella finding.'
  );
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
  const [qaRationale, setQaRationale] = useState('Lab re-test SPL-99824-B satisfies negative culture release criterion under FDA BAM Ch. 5.');
  const [coordRationale, setCoordRationale] = useState('Confirmed re-test documentation attached and validated with lab director. Authorizing inventory release.');

  // Non-Response 21 CFR § 7.49 Form State
  const [regFilingId, setRegFilingId] = useState('FDA-NONRESP-2026-0814-06');
  const [attemptCount, setAttemptCount] = useState(3);
  const [goodFaithNotes, setGoodFaithNotes] = useState(
    '3 documented phone/certified mail outreach attempts without response. Escalated to FDA District Office pursuant to 21 CFR § 7.49.'
  );

  // Refs for modal focus management
  const phoneFirstInputRef = useRef(null);
  const releaseFirstInputRef = useRef(null);
  const nonResponseFirstInputRef = useRef(null);

  const isQaApproved = approvals?.some((a) => a.decision === 'approved' && a.approval_type === 'containment');
  const isOutboxDispatched = ['ack_monitoring', 'effectiveness_check', 'closed'].includes(phase);
  const isAckResolved = !closureGate?.is_blocked && isOutboxDispatched;
  const isClosed = phase === 'closed';

  // Dual-signature detection from projection approvals
  const qaReleaseApp = approvals?.find((a) => a.approval_type === 'release' && a.approver_role === 'qa');
  const closureReleaseApp = approvals?.find((a) => a.approval_type === 'release' && a.approver_role === 'closure_authority');
  const hasReleaseAction = containmentActions?.some((a) => a.action_type === 'release_hold');
  const isStep1Done = !!qaReleaseApp;
  const isStep2Done = hasReleaseAction || !!closureReleaseApp;

  // Derive outstanding acknowledgement ID dynamically without hardcoding
  const outstandingAcks =
    closureGate?.outstanding_acknowledgements || closureGate?.blocking_ack_ids || [];
  const targetAckId = outstandingAcks.length > 0 ? outstandingAcks[0] : null;
  const targetAckLabel = targetAckId || 'outstanding consignee acknowledgement';

  // Modal Escape key and focus trap management
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        setIsPhoneModalOpen(false);
        setIsReleaseModalOpen(false);
        setIsNonResponseModalOpen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  useEffect(() => {
    if (isPhoneModalOpen && phoneFirstInputRef.current) {
      phoneFirstInputRef.current.focus();
    }
  }, [isPhoneModalOpen]);

  useEffect(() => {
    if (isReleaseModalOpen && releaseFirstInputRef.current) {
      releaseFirstInputRef.current.focus();
    }
  }, [isReleaseModalOpen]);

  useEffect(() => {
    if (isNonResponseModalOpen && nonResponseFirstInputRef.current) {
      nonResponseFirstInputRef.current.focus();
    }
  }, [isNonResponseModalOpen]);

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
    // Step 1 uses qaRationale; Step 2 uses coordRationale (Closure Authority rationale)
    onReleaseHold({
      retest_doc_id: retestDocId,
      retest_doc_hash: retestDocHash,
      rationale: isStep1Done ? coordRationale : qaRationale,
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
    <div className="card-panel" style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <div className="section-label" style={{ marginBottom: '2px' }}>Governance & Authorization</div>
          <h2 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <UserCheck size={15} style={{ color: 'var(--accent-primary)' }} />
            Human decision gates (Separation of Duties)
          </h2>
        </div>

        {isQaApproved && (
          <span className="status-tag status-tag-success">
            <span className="status-dot status-dot-success" />
            AUTH-HOLD-01 (Firm Quarantine)
          </span>
        )}
      </div>

      {/* Decision Actions Grid */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
        {/* Gate 1: QA Containment Approval with Inline Rationale Input (Group 4c) */}
        <div
          style={{
            background: 'var(--bg-surface-subtle)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-md)',
            padding: '12px',
            display: 'flex',
            flexDirection: 'column',
            gap: '8px',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
            <div>
              <div style={{ fontWeight: 600, fontSize: '13px', color: 'var(--text-primary)' }}>
                1. Approve Firm Quarantine
              </div>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                Role: <span style={{ color: 'var(--text-secondary)' }}>QA Lead</span> — Converts provisional 30m soft hold into authorized firm quarantine.
              </div>
            </div>

            <button
              className={`btn ${!isQaApproved && !isClosed ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => onApproveContainment(rationale)}
              disabled={loading || isQaApproved || isClosed}
              title="QA Lead sign-off: converts provisional 30m soft hold into authorized firm quarantine"
            >
              <Lock size={13} />
              {isQaApproved ? 'Quarantine Approved' : 'Approve Firm Quarantine (QA)'}
            </button>
          </div>

          {!isQaApproved && !isClosed && (
            <div style={{ marginTop: '4px' }}>
              <label className="section-label" style={{ display: 'block', marginBottom: '4px', fontSize: '10px' }}>
                QA Approval Rationale (Immutably logged to audit stream)
              </label>
              <textarea
                value={rationale}
                onChange={(e) => setRationale(e.target.value)}
                rows={2}
                disabled={isClosed}
                style={{ width: '100%', resize: 'vertical', fontSize: '12px', lineHeight: '1.4' }}
                placeholder="Enter QA approval rationale..."
              />
            </div>
          )}
        </div>

        {/* Gate 2: Dispatch Outbox */}
        <div
          style={{
            background: 'var(--bg-surface-subtle)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-md)',
            padding: '12px',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: '8px',
          }}
        >
          <div>
            <div style={{ fontWeight: 600, fontSize: '13px', color: 'var(--text-primary)' }}>
              2. Dispatch Recall Outbox
            </div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
              Role: <span style={{ color: 'var(--text-secondary)' }}>Customer Operations</span> — Dispatches formal recall notices to all consignees.
            </div>
          </div>

          <button
            className="btn btn-secondary"
            onClick={onDispatchOutbox}
            disabled={loading || !isQaApproved || isOutboxDispatched || isClosed}
            title="Customer Operations sign-off: dispatch formal recall notices to all consignees"
          >
            <Send size={13} />
            {isOutboxDispatched ? 'Outbox Dispatched' : 'Dispatch Recall Outbox (Ops)'}
          </button>
        </div>

        {/* Gate 3: Verify Consignee Attestation via Phone */}
        <div
          style={{
            background: 'var(--bg-surface-subtle)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-md)',
            padding: '12px',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: '8px',
          }}
        >
          <div>
            <div style={{ fontWeight: 600, fontSize: '13px', color: 'var(--text-primary)' }}>
              3. Verify Consignee Attestation
            </div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
              Role: <span style={{ color: 'var(--text-secondary)' }}>Customer Operations</span> — Signs phone attestation verifying {targetAckLabel}.
            </div>
          </div>

          <button
            className="btn btn-secondary"
            onClick={() => setIsPhoneModalOpen(true)}
            disabled={loading || !isOutboxDispatched || isAckResolved || isClosed}
            title={`Record signed phone attestation verifying ${targetAckLabel} receipt`}
          >
            <PhoneCall size={13} />
            {isAckResolved ? (targetAckId ? `${targetAckId} Resolved` : 'Attestation Resolved') : 'Verify Phone Attestation'}
          </button>
        </div>

        {/* Gate 4: Dual-Signature Release Rail & Status (Group 4b) */}
        <div
          style={{
            background: 'var(--bg-surface-subtle)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-md)',
            padding: '12px',
            display: 'flex',
            flexDirection: 'column',
            gap: '8px',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
            <div>
              <div style={{ fontWeight: 600, fontSize: '13px', color: 'var(--text-primary)' }}>
                4. Dual-Signature Hold Release Rail
              </div>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                Requires QA Lead biological clearance followed by distinct Closure Authority inventory release.
              </div>
            </div>

            <button
              className="btn btn-secondary"
              onClick={() => setIsReleaseModalOpen(true)}
              disabled={loading || !isQaApproved || isStep2Done || isClosed}
              title="Execute sequential release step"
            >
              <FileCheck size={13} />
              {isStep2Done
                ? 'Hold Released'
                : isStep1Done
                ? 'Sign Step 2 (Closure Auth)'
                : 'Sign Step 1 (QA Lead)'}
            </button>
          </div>

          {/* Dual-Signature Rail Step Status Indicators */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginTop: '4px' }}>
            <div
              style={{
                background: 'var(--bg-surface)',
                border: `1px solid ${isStep1Done ? 'rgba(34, 197, 94, 0.3)' : 'var(--border-subtle)'}`,
                borderRadius: 'var(--radius-sm)',
                padding: '6px 10px',
                fontSize: '11px',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
              }}
            >
              <span className={`status-dot ${isStep1Done ? 'status-dot-success' : 'status-dot-neutral'}`} />
              <div style={{ flex: 1 }}>
                <span style={{ fontWeight: 600, color: isStep1Done ? 'var(--status-success-text)' : 'var(--text-secondary)' }}>
                  Step 1: QA Clearance
                </span>
                <div style={{ color: 'var(--text-muted)', fontSize: '10px' }}>
                  {qaReleaseApp ? `Signed by ${qaReleaseApp.approver_id}` : 'Awaiting biological clearance'}
                </div>
              </div>
            </div>

            <div
              style={{
                background: 'var(--bg-surface)',
                border: `1px solid ${isStep2Done ? 'rgba(34, 197, 94, 0.3)' : 'var(--border-subtle)'}`,
                borderRadius: 'var(--radius-sm)',
                padding: '6px 10px',
                fontSize: '11px',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
              }}
            >
              <span className={`status-dot ${isStep2Done ? 'status-dot-success' : 'status-dot-neutral'}`} />
              <div style={{ flex: 1 }}>
                <span style={{ fontWeight: 600, color: isStep2Done ? 'var(--status-success-text)' : 'var(--text-secondary)' }}>
                  Step 2: Operational Release
                </span>
                <div style={{ color: 'var(--text-muted)', fontSize: '10px' }}>
                  {isStep2Done ? 'Inventory released' : isStep1Done ? 'Ready for Closure Authority' : 'Locked'}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Gate 5: Non-Response Closure (21 CFR § 7.49) */}
        <div
          style={{
            background: 'var(--bg-surface-subtle)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-md)',
            padding: '12px',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: '8px',
          }}
        >
          <div>
            <div style={{ fontWeight: 600, fontSize: '13px', color: 'var(--text-primary)' }}>
              5. Non-Response Closure (§ 7.49)
            </div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
              Role: <span style={{ color: 'var(--text-secondary)' }}>Closure Authority</span> — Documents certified non-response and refers to FDA District Office.
            </div>
          </div>

          <button
            className="btn btn-secondary"
            onClick={() => setIsNonResponseModalOpen(true)}
            disabled={loading || !isOutboxDispatched || isClosed}
            title="Document certified non-response under 21 CFR § 7.49 and refer to FDA District Office"
          >
            <ShieldCheck size={13} />
            Non-Response Close (§ 7.49)
          </button>
        </div>

        {/* Gate 6: Request Closure */}
        <div
          style={{
            background: 'var(--bg-surface-subtle)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-md)',
            padding: '12px',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: '8px',
          }}
        >
          <div>
            <div style={{ fontWeight: 600, fontSize: '13px', color: 'var(--text-primary)' }}>
              6. Request Incident Closure
            </div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
              Role: <span style={{ color: 'var(--text-secondary)' }}>Closure Authority</span> — Submits for case closure disposition.
            </div>
          </div>

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
                <h3 style={{ fontSize: '14px', fontWeight: 600 }}>Phone Attestation Record ({targetAckLabel})</h3>
              </div>
              <button className="btn btn-ghost" style={{ padding: '4px' }} onClick={() => setIsPhoneModalOpen(false)}>
                <X size={16} />
              </button>
            </div>

            <form onSubmit={handlePhoneSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '10px', fontSize: '12px' }}>
              <div>
                <label className="section-label" style={{ display: 'block', marginBottom: '2px' }}>Caller Identifier</label>
                <input
                  ref={phoneFirstInputRef}
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

      {/* MODAL 2: Dual-Signature Release Rail Modal (Group 1b & 5c) */}
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
                <h3 style={{ fontSize: '14px', fontWeight: 600 }}>
                  {isStep1Done ? 'Step 2 of 2 — Closure authority release' : 'Step 1 of 2 — QA biological clearance'}
                </h3>
              </div>
              <button className="btn btn-ghost" style={{ padding: '4px' }} onClick={() => setIsReleaseModalOpen(false)}>
                <X size={16} />
              </button>
            </div>

            <form onSubmit={handleReleaseSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '10px', fontSize: '12px' }}>
              <div style={{ background: 'var(--bg-surface-subtle)', padding: '8px 10px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)', fontSize: '11px', color: 'var(--text-muted)' }}>
                {isStep1Done
                  ? 'Step 1 signed by QA Lead. Current role must be Closure Authority to authorize final operational inventory release.'
                  : 'Step 1: Current role must be QA Lead to record biological clearance against verified negative laboratory re-test.'}
              </div>

              <div>
                <label className="section-label" style={{ display: 'block', marginBottom: '2px' }}>Lab Re-test Document ID</label>
                <input
                  ref={releaseFirstInputRef}
                  type="text"
                  value={retestDocId}
                  onChange={(e) => setRetestDocId(e.target.value)}
                  style={{ width: '100%' }}
                  readOnly={isStep1Done}
                  required
                />
              </div>

              <div>
                <label className="section-label" style={{ display: 'block', marginBottom: '2px' }}>
                  Re-test SHA-256 Digest {isStep1Done ? '(from attached re-test document)' : ''}
                </label>
                <input
                  type="text"
                  value={retestDocHash}
                  onChange={(e) => setRetestDocHash(e.target.value)}
                  className="mono-val"
                  style={{ width: '100%', fontSize: '11px' }}
                  readOnly={isStep1Done}
                  required
                />
              </div>

              {!isStep1Done ? (
                <div>
                  <label className="section-label" style={{ display: 'block', marginBottom: '2px' }}>QA Clearance Rationale</label>
                  <input
                    type="text"
                    value={qaRationale}
                    onChange={(e) => setQaRationale(e.target.value)}
                    style={{ width: '100%' }}
                    placeholder="Enter QA biological clearance rationale..."
                    required
                  />
                </div>
              ) : (
                <div>
                  <label className="section-label" style={{ display: 'block', marginBottom: '2px' }}>Closure Authority Release Rationale</label>
                  <input
                    type="text"
                    value={coordRationale}
                    onChange={(e) => setCoordRationale(e.target.value)}
                    style={{ width: '100%' }}
                    placeholder="Enter Closure Authority release rationale..."
                    required
                  />
                </div>
              )}

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '10px' }}>
                <button type="button" className="btn btn-ghost" onClick={() => setIsReleaseModalOpen(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary">
                  {isStep1Done ? 'Sign Step 2 (Closure Release)' : 'Sign Step 1 (QA Clearance)'}
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
                  ref={nonResponseFirstInputRef}
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
