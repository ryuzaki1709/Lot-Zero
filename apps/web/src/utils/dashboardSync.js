/**
 * CaseDashboard synchronization and projection-derivation utilities.
 */

export function deriveSummaryFromProjection(proj) {
  if (!proj?.header?.case_id) return null;
  const phase = proj.header.phase || 'signal_received';
  const openHoldQty =
    Number(proj.metrics?.provisional_hold_quantity || 0) +
    Number(proj.metrics?.firm_quarantine_quantity || 0) +
    Number(proj.metrics?.authorized_hold_quantity || 0);
  const isHoldActive = openHoldQty > 0 && phase !== 'closed' && phase !== 'released';
  const isQaApproved = proj.approvals?.some(
    (a) => a.approval_type === 'containment' && a.decision === 'approved'
  );
  const hasPendingQa =
    (phase === 'provisional_containment' || phase === 'scope_review') &&
    !isQaApproved &&
    phase !== 'closed';
  const rejectedAcks = (proj.acknowledgements || []).filter((a) => a.status === 'rejected');
  return {
    case_id: proj.header.case_id,
    tenant_id: proj.header.tenant_id || 'EVAL-TENANT-01',
    phase: phase,
    case_version: Number(proj.header.case_version || 0),
    has_open_holds: isHoldActive,
    open_hold_quantity: isHoldActive ? openHoldQty : 0.0,
    has_pending_qa: hasPendingQa,
    pending_qa_type: hasPendingQa ? 'containment' : null,
    has_rejected_acks: rejectedAcks.length > 0,
    rejected_ack_count: rejectedAcks.length,
    last_event_type: 'UPDATED',
    updated_at: proj.header.updated_at || new Date().toISOString(),
  };
}

export function matchesFilter(caseSummary, filter) {
  if (!caseSummary) return false;
  if (filter === 'open_holds') return caseSummary.has_open_holds;
  if (filter === 'pending_qa') return caseSummary.has_pending_qa;
  if (filter === 'blocked_by_rejections') return caseSummary.has_rejected_acks;
  return true;
}

export function mergeCasesWithProjection(serverCases, currentProj, filter = 'all') {
  const projSummary = deriveSummaryFromProjection(currentProj);
  let merged = Array.isArray(serverCases) ? [...serverCases] : [];
  if (projSummary) {
    const existingIdx = merged.findIndex((c) => c.case_id === projSummary.case_id);
    if (existingIdx >= 0) {
      merged[existingIdx] = projSummary;
    } else {
      merged.unshift(projSummary);
    }
  }
  return merged.filter((c) => matchesFilter(c, filter));
}
