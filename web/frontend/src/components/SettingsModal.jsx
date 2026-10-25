import React, { useState, useEffect } from 'react';
import { X, Save, Key, ShieldCheck, Server, Check, Youtube, ExternalLink, LogOut } from 'lucide-react';

export default function SettingsModal({ isOpen, onClose, settings, onSaveSettings, onRefreshSettings }) {
  const [publicKey, setPublicKey] = useState('');
  const [secretKey, setSecretKey] = useState('');
  const [host, setHost] = useState('https://cloud.langfuse.com');
  const [ollamaHost, setOllamaHost] = useState('http://localhost:11434');

  // YouTube OAuth Credentials
  const [ytClientId, setYtClientId] = useState('');
  const [ytClientSecret, setYtClientSecret] = useState('');

  const [isSaving, setIsSaving] = useState(false);
  const [savedSuccess, setSavedSuccess] = useState(false);

  useEffect(() => {
    if (settings) {
      setPublicKey(settings.langfuse_public_key || '');
      setHost(settings.langfuse_host || 'https://cloud.langfuse.com');
      setOllamaHost(settings.ollama_host || 'http://localhost:11434');
      setYtClientId(settings.youtube_client_id || '');
      setSecretKey('');
      setYtClientSecret('');
    }
  }, [settings, isOpen]);

  if (!isOpen) return null;

  const ytStatus = settings?.youtube_status || {};
  const isYtConnected = ytStatus.connected;
  const isYtConfigured = ytStatus.configured;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsSaving(true);
    try {
      await onSaveSettings({
        langfuse_public_key: publicKey,
        langfuse_secret_key: secretKey,
        langfuse_host: host,
        ollama_host: ollamaHost,
        youtube_client_id: ytClientId,
        youtube_client_secret: ytClientSecret
      });
      setSavedSuccess(true);
      setTimeout(() => {
        setSavedSuccess(false);
        onClose();
      }, 1000);
    } catch (err) {
      alert(`Failed to save settings: ${err.message}`);
    } finally {
      setIsSaving(false);
    }
  };

  const handleStartOAuth = async () => {
    try {
      const redirectUri = `${window.location.origin}/api/youtube/auth/callback`;
      const res = await fetch(`/api/youtube/auth/url?redirect_uri=${encodeURIComponent(redirectUri)}`);
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Failed to start OAuth');
      }
      const { auth_url } = await res.json();
      window.location.href = auth_url;
    } catch (err) {
      alert(`OAuth Error: ${err.message}. Please save Client ID & Secret first.`);
    }
  };

  const handleDisconnectYouTube = async () => {
    if (!confirm('Disconnect YouTube account?')) return;
    try {
      await fetch('/api/youtube/disconnect', { method: 'POST' });
      if (onRefreshSettings) onRefreshSettings();
    } catch (err) {
      console.error('Failed to disconnect YouTube:', err);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card" style={{ maxWidth: 560 }} onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Key size={18} color="var(--accent-primary)" />
            <h3 style={{ fontSize: 16, fontWeight: 700, fontFamily: 'var(--font-display)' }}>
              Studio Settings & API Integrations
            </h3>
          </div>
          <button type="button" className="btn-icon" onClick={onClose}>
            <X size={16} />
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="modal-body" style={{ maxHeight: '70vh', overflowY: 'auto' }}>
            <div style={{ fontSize: 12, color: 'var(--text-secondary)', background: 'var(--bg-surface)', padding: 10, borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
              Credentials are saved persistently to your local <code style={{ color: 'var(--accent-primary)', fontFamily: 'var(--font-mono)' }}>.env</code> file and applied immediately to both UI and CLI.
            </div>

            {/* YouTube Section */}
            <div style={{ border: '1px solid var(--border-subtle)', background: 'var(--bg-input)', padding: 14, borderRadius: 'var(--radius-md)' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontWeight: 700, fontSize: 13, color: '#ef4444' }}>
                  <Youtube size={16} /> YouTube Data API & OAuth
                </div>
                <span
                  className="status-pill"
                  style={{
                    fontSize: 10,
                    padding: '2px 8px',
                    borderColor: isYtConnected ? 'rgba(16, 185, 129, 0.4)' : 'rgba(239, 68, 68, 0.4)',
                    color: isYtConnected ? 'var(--accent-success)' : 'var(--text-muted)'
                  }}
                >
                  {isYtConnected ? `Connected (${ytStatus.channel?.title || 'Account'})` : 'Not Connected'}
                </span>
              </div>

              <div className="form-group" style={{ marginBottom: 10 }}>
                <label className="form-label" style={{ fontSize: 11 }}>YouTube OAuth Client ID</label>
                <input
                  type="text"
                  className="input-text"
                  placeholder="xxxx.apps.googleusercontent.com"
                  value={ytClientId}
                  onChange={(e) => setYtClientId(e.target.value)}
                />
              </div>

              <div className="form-group" style={{ marginBottom: 10 }}>
                <label className="form-label" style={{ fontSize: 11 }}>YouTube OAuth Client Secret</label>
                <input
                  type="password"
                  className="input-text"
                  placeholder={settings?.has_youtube_secret ? `Current: ${settings.youtube_client_secret_masked} (leave empty to keep unchanged)` : "GOCSPX-..."}
                  value={ytClientSecret}
                  onChange={(e) => setYtClientSecret(e.target.value)}
                />
              </div>

              <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                {isYtConnected ? (
                  <button
                    type="button"
                    className="btn btn-secondary"
                    style={{ fontSize: 11, padding: '4px 10px', color: 'var(--accent-danger)' }}
                    onClick={handleDisconnectYouTube}
                  >
                    <LogOut size={12} /> Disconnect Channel
                  </button>
                ) : (
                  <button
                    type="button"
                    className="btn btn-primary"
                    style={{ background: '#ef4444', borderColor: '#ef4444', fontSize: 11, padding: '4px 12px' }}
                    onClick={handleStartOAuth}
                  >
                    <Youtube size={13} /> Authorize YouTube Account via OAuth
                  </button>
                )}
              </div>
            </div>

            {/* Langfuse Observability Section */}
            <div style={{ marginTop: 8 }}>
              <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 8, color: 'var(--text-secondary)' }}>
                Langfuse Observability
              </div>

              <div className="form-group">
                <label className="form-label" style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11 }}>
                  <Key size={11} /> Langfuse Public Key
                </label>
                <input
                  type="text"
                  className="input-text"
                  placeholder="pk-lf-..."
                  value={publicKey}
                  onChange={(e) => setPublicKey(e.target.value)}
                />
              </div>

              <div className="form-group">
                <label className="form-label" style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11 }}>
                  <ShieldCheck size={11} /> Langfuse Secret Key
                </label>
                <input
                  type="password"
                  className="input-text"
                  placeholder={settings?.has_langfuse_secret ? `Current: ${settings.langfuse_secret_key_masked} (leave empty to keep unchanged)` : "sk-lf-..."}
                  value={secretKey}
                  onChange={(e) => setSecretKey(e.target.value)}
                />
              </div>

              <div className="form-group">
                <label className="form-label" style={{ fontSize: 11 }}>Langfuse Host URL</label>
                <input
                  type="text"
                  className="input-text"
                  placeholder="https://cloud.langfuse.com"
                  value={host}
                  onChange={(e) => setHost(e.target.value)}
                />
              </div>
            </div>

            {/* Ollama Section */}
            <div className="form-group">
              <label className="form-label" style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11 }}>
                <Server size={11} /> Ollama Host
              </label>
              <input
                type="text"
                className="input-text"
                placeholder="http://localhost:11434"
                value={ollamaHost}
                onChange={(e) => setOllamaHost(e.target.value)}
              />
            </div>
          </div>

          <div className="modal-footer">
            <button type="button" className="btn btn-secondary" onClick={onClose} disabled={isSaving}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={isSaving}>
              {savedSuccess ? (
                <>
                  <Check size={14} color="var(--accent-success)" /> Saved to .env!
                </>
              ) : isSaving ? (
                'Saving...'
              ) : (
                <>
                  <Save size={14} /> Save Configuration
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
