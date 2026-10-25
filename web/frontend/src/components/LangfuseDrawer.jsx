import React, { useRef, useEffect } from 'react';
import { X, ExternalLink, Terminal, Activity, CheckCircle2, AlertCircle } from 'lucide-react';

export default function LangfuseDrawer({ isOpen, onClose, logs, settings, onClearLogs }) {
  const terminalRef = useRef(null);

  // Auto-scroll terminal when new logs arrive
  useEffect(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  }, [logs]);

  const isTracking = settings?.is_langfuse_enabled;

  return (
    <div className={`diagnostics-drawer ${isOpen ? '' : 'closed'}`}>
      <div className="drawer-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Activity size={18} color="var(--accent-primary)" />
          <h3 style={{ fontSize: 16, fontWeight: 700, fontFamily: 'var(--font-display)' }}>
            Langfuse Diagnostics & Logs
          </h3>
        </div>
        <button type="button" className="btn-icon" onClick={onClose}>
          <X size={16} />
        </button>
      </div>

      <div className="drawer-body">
        {/* Status Card */}
        <div className="studio-card" style={{ padding: 14 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
            <span style={{ fontSize: 12, fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-muted)' }}>
              Observability Status
            </span>
            <span
              className="status-pill"
              style={{
                borderColor: isTracking ? 'rgba(16, 185, 129, 0.4)' : 'rgba(239, 68, 68, 0.4)',
                color: isTracking ? 'var(--accent-success)' : 'var(--text-muted)'
              }}
            >
              {isTracking ? <CheckCircle2 size={12} /> : <AlertCircle size={12} />}
              {isTracking ? 'Tracking Active' : 'Keys Missing / Inactive'}
            </span>
          </div>

          <div style={{ fontSize: 12, display: 'flex', flexDirection: 'column', gap: 4, color: 'var(--text-secondary)' }}>
            <div>
              Host: <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>{settings?.langfuse_host || 'https://cloud.langfuse.com'}</span>
            </div>
            <div>
              Public Key: <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>{settings?.langfuse_public_key || 'Not configured'}</span>
            </div>
          </div>

          {isTracking && (
            <a
              href={settings?.langfuse_host || 'https://cloud.langfuse.com'}
              target="_blank"
              rel="noreferrer"
              className="btn btn-secondary btn-full"
              style={{ marginTop: 12, textDecoration: 'none', fontSize: 12, padding: '6px 12px' }}
            >
              <ExternalLink size={13} /> Open Langfuse Cloud Console
            </a>
          )}
        </div>

        {/* Live Logs Terminal */}
        <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
            <span style={{ fontSize: 12, fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 6 }}>
              <Terminal size={14} /> Live Pipeline Output
            </span>
            <button
              type="button"
              className="btn-icon"
              style={{ fontSize: 11, padding: '2px 8px' }}
              onClick={onClearLogs}
            >
              Clear
            </button>
          </div>

          <div className="log-terminal" ref={terminalRef}>
            {logs && logs.length > 0 ? (
              logs.map((line, idx) => (
                <div key={idx} style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                  {line}
                </div>
              ))
            ) : (
              <div style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>
                Pipeline execution logs and Langfuse events will appear here in real time...
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
