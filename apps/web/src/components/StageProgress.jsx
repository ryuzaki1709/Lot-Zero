import React from 'react';
import {
  FileSearch,
  Network,
  Lock,
  UserCheck,
  Send,
  CheckCircle2,
  AlertOctagon,
  ShieldCheck,
} from 'lucide-react';

export function StageProgress({ phase, metrics, closureGate }) {
  const isBlocked = closureGate?.is_blocked;
  const isClosed = phase === 'closed';

  const stages = [
    {
      id: 'signal_received',
      num: '01',
      name: 'Signal Ingestion',
      desc: 'Pathogen lab notice',
      icon: FileSearch,
      isDone: phase !== 'signal_received',
      isActive: phase === 'signal_received',
    },
    {
      id: 'scope_review',
      num: '02',
      name: 'Trace & Scope',
      desc: 'Genealogy graph traversal',
      icon: Network,
      isDone: ['provisional_containment', 'action_review', 'ack_monitoring', 'effectiveness_check', 'closed'].includes(phase),
      isActive: phase === 'scope_review',
    },
    {
      id: 'provisional_containment',
      num: '03',
      name: 'Provisional Hold',
      desc: '30m soft hold (EVAL-HOLD-01)',
      icon: Lock,
      isDone: ['action_review', 'ack_monitoring', 'effectiveness_check', 'closed'].includes(phase),
      isActive: phase === 'provisional_containment',
    },
    {
      id: 'action_review',
      num: '04',
      name: 'QA & Coord Approval',
      desc: 'Dual-role gate signed',
      icon: UserCheck,
      isDone: ['ack_monitoring', 'effectiveness_check', 'closed'].includes(phase),
      isActive: phase === 'action_review',
    },
    {
      id: 'ack_monitoring',
      num: '05',
      name: 'Consignee Outreach',
      desc: 'Outbox & acknowledgements',
      icon: Send,
      isDone: ['effectiveness_check', 'closed'].includes(phase),
      isActive: phase === 'ack_monitoring',
    },
    {
      id: 'effectiveness_check',
      num: '06',
      name: 'Incident Disposition',
      desc: isClosed ? 'Closed & archived' : (isBlocked ? 'Blocked (ACK-006 pending)' : 'Ready to close'),
      icon: isClosed ? ShieldCheck : (isBlocked ? AlertOctagon : CheckCircle2),
      isDone: isClosed,
      isActive: phase === 'effectiveness_check' || isClosed,
      isWarning: isBlocked && !isClosed,
      isSuccess: isClosed,
    },
  ];

  return (
    <div
      className="card-panel"
      style={{
        margin: '0 24px 16px',
        padding: '12px 16px',
        overflowX: 'auto',
      }}
    >
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(6, minmax(140px, 1fr))',
          gap: '8px',
          minWidth: '880px',
        }}
      >
        {stages.map((stage) => {
          const Icon = stage.icon;
          let borderColor = 'var(--border-subtle)';
          let bgColor = 'transparent';
          let statusDot = 'status-dot-neutral';
          let labelColor = 'var(--text-muted)';
          let titleColor = 'var(--text-secondary)';

          if (stage.isDone) {
            borderColor = 'rgba(34, 197, 94, 0.25)';
            bgColor = 'rgba(34, 197, 94, 0.03)';
            statusDot = 'status-dot-success';
            titleColor = 'var(--text-primary)';
          } else if (stage.isActive) {
            if (stage.isWarning) {
              borderColor = 'rgba(245, 158, 11, 0.4)';
              bgColor = 'rgba(245, 158, 11, 0.05)';
              statusDot = 'status-dot-warning';
              titleColor = 'var(--status-warning-text)';
            } else if (stage.isSuccess) {
              borderColor = 'rgba(34, 197, 94, 0.4)';
              bgColor = 'rgba(34, 197, 94, 0.05)';
              statusDot = 'status-dot-success';
              titleColor = 'var(--status-success-text)';
            } else {
              borderColor = 'var(--accent-primary)';
              bgColor = 'rgba(6, 182, 212, 0.04)';
              statusDot = 'status-dot-success';
              titleColor = 'var(--text-primary)';
            }
          }

          return (
            <div
              key={stage.id}
              style={{
                background: bgColor,
                border: `1px solid ${borderColor}`,
                borderRadius: 'var(--radius-md)',
                padding: '10px 12px',
                display: 'flex',
                flexDirection: 'column',
                gap: '4px',
                transition: 'border-color var(--transition-fast), background-color var(--transition-fast)',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span className="section-label" style={{ fontSize: '10px' }}>
                  {stage.num}
                </span>
                <span className={`status-dot ${statusDot}`} />
              </div>

              <div style={{ fontSize: '13px', fontWeight: 600, color: titleColor, display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Icon size={14} style={{ flexShrink: 0, opacity: stage.isActive ? 1 : 0.7 }} />
                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{stage.name}</span>
              </div>

              <div style={{ fontSize: '11px', color: labelColor, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {stage.desc}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
