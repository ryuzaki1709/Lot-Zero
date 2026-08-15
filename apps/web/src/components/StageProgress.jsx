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
      name: '01. Ingestion',
      desc: 'Lab Salmonella Notice',
      icon: FileSearch,
      isDone: phase !== 'signal_received',
      isActive: phase === 'signal_received',
    },
    {
      id: 'scope_review',
      name: '02. Trace & Scope',
      desc: 'Bidirectional DAG',
      icon: Network,
      isDone: ['provisional_containment', 'action_review', 'ack_monitoring', 'effectiveness_check', 'closed'].includes(phase),
      isActive: phase === 'scope_review',
    },
    {
      id: 'provisional_containment',
      name: '03. Provisional Hold',
      desc: '30m Soft Hold (EVAL-HOLD-01)',
      icon: Lock,
      isDone: ['action_review', 'ack_monitoring', 'effectiveness_check', 'closed'].includes(phase),
      isActive: phase === 'provisional_containment',
    },
    {
      id: 'action_review',
      name: '04. QA & Coord Approval',
      desc: 'Dual Role Gate Signed',
      icon: UserCheck,
      isDone: ['ack_monitoring', 'effectiveness_check', 'closed'].includes(phase),
      isActive: phase === 'action_review',
    },
    {
      id: 'ack_monitoring',
      name: '05. Consignee Outreach',
      desc: 'Outbox & Acknowledgements',
      icon: Send,
      isDone: ['effectiveness_check', 'closed'].includes(phase),
      isActive: phase === 'ack_monitoring',
    },
    {
      id: 'effectiveness_check',
      name: '06. Disposition',
      desc: isClosed ? 'Closed & Archived' : (isBlocked ? 'Blocked (ACK-006 Pending)' : 'Ready to Close'),
      icon: isClosed ? ShieldCheck : (isBlocked ? AlertOctagon : CheckCircle2),
      isDone: isClosed,
      isActive: phase === 'effectiveness_check' || isClosed,
      isWarning: isBlocked && !isClosed,
      isSuccess: isClosed,
    },
  ];

  return (
    <div
      className="glass-panel"
      style={{
        margin: '0 20px 20px',
        padding: '14px 18px',
        overflowX: 'auto',
      }}
    >
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(6, minmax(150px, 1fr))',
          gap: '10px',
          minWidth: '940px',
        }}
      >
        {stages.map((stage) => {
          const Icon = stage.icon;
          let statusColor = 'var(--text-muted)';
          let bgStyle = 'rgba(255, 255, 255, 0.02)';
          let borderStyle = 'var(--border-subtle)';

          if (stage.isDone) {
            statusColor = 'var(--accent-emerald)';
            bgStyle = 'rgba(16, 185, 129, 0.08)';
            borderStyle = 'rgba(16, 185, 129, 0.3)';
          } else if (stage.isActive) {
            if (stage.isWarning) {
              statusColor = 'var(--accent-amber)';
              bgStyle = 'rgba(245, 158, 11, 0.12)';
              borderStyle = 'rgba(245, 158, 11, 0.4)';
            } else if (stage.isSuccess) {
              statusColor = 'var(--accent-emerald)';
              bgStyle = 'rgba(16, 185, 129, 0.15)';
              borderStyle = 'var(--accent-emerald)';
            } else {
              statusColor = 'var(--accent-cyan)';
              bgStyle = 'rgba(6, 182, 212, 0.12)';
              borderStyle = 'var(--border-active)';
            }
          }

          return (
            <div
              key={stage.id}
              style={{
                background: bgStyle,
                border: `1px solid ${borderStyle}`,
                borderRadius: '10px',
                padding: '10px 12px',
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                position: 'relative',
              }}
            >
              <div
                style={{
                  width: '30px',
                  height: '30px',
                  borderRadius: '8px',
                  background: 'rgba(0, 0, 0, 0.35)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                }}
              >
                <Icon size={16} color={statusColor} />
              </div>
              <div style={{ minWidth: 0 }}>
                <div
                  style={{
                    fontSize: '0.78rem',
                    fontWeight: 700,
                    color: stage.isActive ? 'var(--text-primary)' : statusColor,
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                  }}
                >
                  {stage.name}
                </div>
                <div
                  style={{
                    fontSize: '0.7rem',
                    color: 'var(--text-secondary)',
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                  }}
                >
                  {stage.desc}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
