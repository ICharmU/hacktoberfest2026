import React, { useState, useEffect } from 'react';
import { X, Save, Key, ShieldCheck, Server, Check } from 'lucide-react';

export default function SettingsModal({ isOpen, onClose, settings, onSaveSettings }) {
  const [publicKey, setPublicKey] = useState('');
  const [secretKey, setSecretKey] = useState('');
  const [host, setHost] = useState('https://cloud.langfuse.com');
  const [ollamaHost, setOllamaHost] = useState('http://localhost:11434');
  const [isSaving, setIsSaving] = useState(false);
  const [savedSuccess, setSavedSuccess] = useState(false);

  useEffect(() => {
    if (settings) {
      setPublicKey(settings.langfuse_public_key || '');
      setHost(settings.langfuse_host || 'https://cloud.langfuse.com');
      setOllamaHost(settings.ollama_host || 'http://localhost:11434');
      setSecretKey('');
    }
  }, [settings, isOpen]);

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsSaving(true);
    try {
      await onSaveSettings({
        langfuse_public_key: publicKey,
        langfuse_secret_key: secretKey,
        langfuse_host: host,
        ollama_host: ollamaHost
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

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Key size={18} color="var(--accent-primary)" />
            <h3 style={{ fontSize: 16, fontWeight: 700, fontFamily: 'var(--font-display)' }}>
              Pipeline & API Configuration
            </h3>
          </div>
          <button type="button" className="btn-icon" onClick={onClose}>
            <X size={16} />
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="modal-body">
            <div style={{ fontSize: 12, color: 'var(--text-secondary)', background: 'var(--bg-surface)', padding: 10, borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
              Settings saved here are persistently written to the local <code style={{ color: 'var(--accent-primary)', fontFamily: 'var(--font-mono)' }}>.env</code> file and applied immediately to both UI and CLI.
            </div>

            <div className="form-group">
              <label className="form-label" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <Key size={12} /> Langfuse Public Key
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
              <label className="form-label" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <ShieldCheck size={12} /> Langfuse Secret Key
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
              <label className="form-label">Langfuse Host URL</label>
              <input
                type="text"
                className="input-text"
                placeholder="https://cloud.langfuse.com"
                value={host}
                onChange={(e) => setHost(e.target.value)}
              />
            </div>

            <div className="form-group">
              <label className="form-label" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <Server size={12} /> Ollama Host
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
