import React from 'react';

export function StageProgress({ phase, metrics, closureGate }) {
  const isBlocked = closureGate?.is_blocked;
  const isClosed = phase === 'closed';

  const blockingAcks =
    closureGate?.outstanding_acknowledgements || closureGate?.blocking_ack_ids || [];
  const blockedDesc =
    blockingAcks.length > 0
      ? `Blocked — ${blockingAcks.join(', ')}`
      : 'Blocked — unverified acknowledgements';

  const stages = [
    {
      id: 'signal_received',
      name: 'Signal ingestion',
      desc: 'Pathogen lab notice',
      isDone: phase !== 'signal_received',
      isActive: phase === 'signal_received',
    },
    {
      id: 'scope_review',
      name: 'Trace & scope',
      desc: 'Genealogy traversal',
      isDone: [
        'provisional_containment',
        'action_review',
        'ack_monitoring',
        'effectiveness_check',
        'closed',
      ].includes(phase),
      isActive: phase === 'scope_review',
    },
    {
      id: 'provisional_containment',
      name: 'Provisional hold',
      desc: '30 min soft hold',
      isDone: ['action_review', 'ack_monitoring', 'effectiveness_check', 'closed'].includes(phase),
      isActive: phase === 'provisional_containment',
    },
    {
      id: 'action_review',
      name: 'Approval',
      desc: 'Dual-role gate',
      isDone: ['ack_monitoring', 'effectiveness_check', 'closed'].includes(phase),
      isActive: phase === 'action_review',
    },
    {
      id: 'ack_monitoring',
      name: 'Outreach',
      desc: 'Consignee outreach',
      isDone: ['effectiveness_check', 'closed'].includes(phase),
      isActive: phase === 'ack_monitoring',
    },
    {
      id: 'effectiveness_check',
      name: 'Disposition',
      desc: isClosed ? 'Closed & archived' : isBlocked ? blockedDesc : 'Ready to close',
      isDone: isClosed,
      isActive: phase === 'effectiveness_check' || isClosed,
      isWarning: isBlocked && !isClosed,
    },
  ];

  return (
    <div className="stepper">
      {stages.map((s) => (
        <div
          key={s.id}
          className={`step ${s.isDone ? 'step-done' : ''} ${
            s.isActive ? (s.isWarning ? 'step-warning' : 'step-active') : ''
          }`}
        >
          <div className="step-name">{s.name}</div>
          <div className="step-desc">{s.desc}</div>
        </div>
      ))}
    </div>
  );
}
