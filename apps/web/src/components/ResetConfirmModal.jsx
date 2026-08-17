import React, { useEffect, useRef } from 'react';
import { AlertTriangle, Trash2, X } from 'lucide-react';

export function ResetConfirmModal({ isOpen, onClose, onConfirm, loading }) {
  const cancelBtnRef = useRef(null);

  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    if (cancelBtnRef.current) cancelBtnRef.current.focus();
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal-panel modal-panel-sm"
        style={{ position: 'relative' }}
        onClick={(e) => e.stopPropagation()}
      >
        <button
          onClick={onClose}
          className="btn btn-ghost"
          style={{
            position: 'absolute',
            top: '16px',
            right: '16px',
            padding: '4px',
          }}
          aria-label="Close dialog"
        >
          <X size={16} />
        </button>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: '28px',
              height: '28px',
              borderRadius: 'var(--radius-sm)',
              background: 'var(--status-danger-bg)',
              color: 'var(--status-danger)',
              border: '1px solid var(--status-danger-border)',
              flexShrink: 0,
            }}
          >
            <AlertTriangle size={15} />
          </div>
          <div>
            <h2 style={{ fontSize: '16px', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
              Reset incident state
            </h2>
          </div>
        </div>

        <p style={{ color: 'var(--text-secondary)', fontSize: '13px', lineHeight: 1.5, margin: '12px 0 16px' }}>
          This action permanently deletes all recorded incident events and cryptographic ledger entries from the persistent SQLite event store. The incident case will return to the unseeded baseline (<code style={{ fontSize: '12px', background: 'var(--bg-surface-subtle)', padding: '2px 4px', borderRadius: '4px' }}>phase: signal_received</code>).
        </p>

        <div style={{
          background: 'var(--bg-surface-subtle)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--radius-sm)',
          padding: '10px 12px',
          fontSize: '12px',
          color: 'var(--status-danger)',
          marginBottom: '20px',
          display: 'flex',
          alignItems: 'center',
          gap: '6px'
        }}>
          <strong>Warning:</strong> This cannot be undone.
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
          <button
            ref={cancelBtnRef}
            type="button"
            className="btn btn-secondary"
            onClick={onClose}
            disabled={loading}
          >
            Cancel
          </button>
          <button
            type="button"
            className="btn btn-danger"
            onClick={() => {
              onConfirm();
              onClose();
            }}
            disabled={loading}
          >
            <Trash2 size={14} />
            Reset State
          </button>
        </div>
      </div>
    </div>
  );
}
