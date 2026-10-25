import React, { useState, useEffect } from 'react';
import {
  X,
  Youtube,
  UploadCloud,
  CheckCircle2,
  ExternalLink,
  Lock,
  Globe,
  EyeOff,
  AlertCircle,
  Loader2,
  LogOut
} from 'lucide-react';

export default function YouTubeUploadModal({
  isOpen,
  onClose,
  video,
  youtubeStatus,
  onRefreshYouTubeStatus,
  onOpenSettings
}) {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [tags, setTags] = useState('');
  const [privacy, setPrivacy] = useState('unlisted');
  const [madeForKids, setMadeForKids] = useState(false);

  const [isUploading, setIsUploading] = useState(false);
  const [uploadPercent, setUploadPercent] = useState(0);
  const [uploadError, setUploadError] = useState(null);
  const [uploadResult, setUploadResult] = useState(null);

  useEffect(() => {
    if (video && isOpen) {
      const meta = video.metadata || {};
      setTitle(video.title ? `${video.title} #shorts` : '');
      const tagsList = video.tags || [];
      const tagsStr = tagsList.map((t) => (t.startsWith('#') ? t : `#${t}`)).join(' ');
      setDescription(video.description ? `${video.description}\n\n${tagsStr}` : tagsStr);
      setTags(tagsList.join(', '));
      setUploadError(null);
      setUploadResult(null);
      setUploadPercent(0);

      // Check if already uploaded
      if (meta.youtube_shorts_url) {
        setUploadResult({
          shorts_url: meta.youtube_shorts_url,
          watch_url: meta.youtube_watch_url,
          video_id: meta.youtube_id
        });
      }
    }
  }, [video, isOpen]);

  if (!isOpen || !video) return null;

  const isConnected = youtubeStatus?.connected;
  const isConfigured = youtubeStatus?.configured;
  const channel = youtubeStatus?.channel;

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
      alert(`OAuth Error: ${err.message}. Make sure YOUTUBE_CLIENT_ID & YOUTUBE_CLIENT_SECRET are configured in Settings.`);
    }
  };

  const handleDisconnect = async () => {
    if (!confirm('Are you sure you want to disconnect your YouTube channel?')) return;
    try {
      await fetch('/api/youtube/disconnect', { method: 'POST' });
      if (onRefreshYouTubeStatus) onRefreshYouTubeStatus();
    } catch (err) {
      console.error('Failed to disconnect:', err);
    }
  };

  const handleUpload = async (e) => {
    e.preventDefault();
    setIsUploading(true);
    setUploadError(null);
    setUploadPercent(15);

    try {
      const parsedTags = tags
        .split(',')
        .map((t) => t.trim())
        .filter(Boolean);

      const res = await fetch(`/api/youtube/upload/${video.id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title,
          description,
          tags: parsedTags,
          privacy_status: privacy,
          made_for_kids: madeForKids
        })
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || 'Upload failed');
      }

      const result = await res.json();
      setUploadPercent(100);
      setUploadResult(result);
    } catch (err) {
      setUploadError(err.message);
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card" style={{ maxWidth: 560 }} onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Youtube size={20} color="#ef4444" />
            <h3 style={{ fontSize: 16, fontWeight: 700, fontFamily: 'var(--font-display)' }}>
              Direct YouTube Shorts Upload
            </h3>
          </div>
          <button type="button" className="btn-icon" onClick={onClose}>
            <X size={16} />
          </button>
        </div>

        <div className="modal-body">
          {/* Connection State Panel */}
          <div
            style={{
              background: 'var(--bg-input)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-md)',
              padding: '12px 16px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between'
            }}
          >
            {isConnected ? (
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                {channel?.thumbnail ? (
                  <img
                    src={channel.thumbnail}
                    alt={channel.title}
                    style={{ width: 34, height: 34, borderRadius: '50%' }}
                  />
                ) : (
                  <div
                    style={{
                      width: 34,
                      height: 34,
                      borderRadius: '50%',
                      background: '#ef4444',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: 'white',
                      fontWeight: 700
                    }}
                  >
                    YT
                  </div>
                )}
                <div>
                  <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>
                    {channel?.title || 'Connected Channel'}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--accent-success)' }}>
                    ● YouTube Account Authorized
                  </div>
                </div>
              </div>
            ) : (
              <div>
                <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)' }}>
                  No YouTube Account Connected
                </div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                  Authenticate via Google OAuth to upload videos directly.
                </div>
              </div>
            )}

            <div>
              {isConnected ? (
                <button
                  type="button"
                  className="btn btn-secondary"
                  style={{ fontSize: 11, padding: '4px 8px', color: 'var(--accent-danger)' }}
                  onClick={handleDisconnect}
                >
                  <LogOut size={12} /> Disconnect
                </button>
              ) : isConfigured ? (
                <button
                  type="button"
                  className="btn btn-primary"
                  style={{ background: '#ef4444', borderColor: '#ef4444', fontSize: 12, padding: '6px 12px' }}
                  onClick={handleStartOAuth}
                >
                  <Youtube size={14} /> Connect Channel
                </button>
              ) : (
                <button
                  type="button"
                  className="btn btn-secondary"
                  style={{ fontSize: 12, padding: '6px 12px' }}
                  onClick={() => {
                    onClose();
                    onOpenSettings();
                  }}
                >
                  Configure Keys
                </button>
              )}
            </div>
          </div>

          {/* Success Banner if Uploaded */}
          {uploadResult && (
            <div
              style={{
                background: 'rgba(16, 185, 129, 0.12)',
                border: '1px solid rgba(16, 185, 129, 0.3)',
                borderRadius: 'var(--radius-md)',
                padding: '14px 16px',
                display: 'flex',
                flexDirection: 'column',
                gap: 8
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--accent-success)', fontWeight: 700, fontSize: 14 }}>
                <CheckCircle2 size={16} /> Successfully Uploaded to YouTube!
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                Your video is published and processing on YouTube Shorts:
              </div>
              <div style={{ display: 'flex', gap: 10, marginTop: 4 }}>
                <a
                  href={uploadResult.shorts_url}
                  target="_blank"
                  rel="noreferrer"
                  className="btn btn-primary"
                  style={{ fontSize: 12, padding: '6px 12px', background: '#ef4444', textDecoration: 'none' }}
                >
                  <ExternalLink size={12} /> View on YouTube Shorts
                </a>
              </div>
            </div>
          )}

          {/* Upload Form */}
          {isConnected && !uploadResult && (
            <form onSubmit={handleUpload}>
              <div className="form-group">
                <label className="form-label">Video Title (max 100 chars)</label>
                <input
                  type="text"
                  maxLength={100}
                  className="input-text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  required
                  disabled={isUploading}
                />
              </div>

              <div className="form-group">
                <label className="form-label">Description & Hashtags</label>
                <textarea
                  className="topic-input-textarea"
                  rows={3}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  disabled={isUploading}
                />
              </div>

              <div className="form-group">
                <label className="form-label">Tags (comma-separated)</label>
                <input
                  type="text"
                  className="input-text"
                  value={tags}
                  onChange={(e) => setTags(e.target.value)}
                  placeholder="shorts, brainrot, history, funny"
                  disabled={isUploading}
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginTop: 12 }}>
                <div>
                  <label className="form-label">Privacy Status</label>
                  <select
                    className="input-text"
                    value={privacy}
                    onChange={(e) => setPrivacy(e.target.value)}
                    disabled={isUploading}
                    style={{ cursor: 'pointer' }}
                  >
                    <option value="unlisted">Unlisted (Recommended)</option>
                    <option value="public">Public</option>
                    <option value="private">Private</option>
                  </select>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', marginTop: 14 }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: 'var(--text-secondary)', cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={madeForKids}
                      onChange={(e) => setMadeForKids(e.target.checked)}
                      disabled={isUploading}
                    />
                    Made for Kids
                  </label>
                </div>
              </div>

              {uploadError && (
                <div style={{ marginTop: 14, color: 'var(--accent-danger)', fontSize: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
                  <AlertCircle size={14} /> {uploadError}
                </div>
              )}

              {isUploading && (
                <div style={{ marginTop: 16 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: 'var(--text-secondary)', marginBottom: 6 }}>
                    <span>Uploading video to YouTube...</span>
                    <span>{uploadPercent}%</span>
                  </div>
                  <div className="progress-bar-track">
                    <div className="progress-bar-fill" style={{ width: `${uploadPercent}%`, background: '#ef4444' }} />
                  </div>
                </div>
              )}

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 20 }}>
                <button type="button" className="btn btn-secondary" onClick={onClose} disabled={isUploading}>
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  style={{ background: '#ef4444', borderColor: '#ef4444' }}
                  disabled={!title.trim() || isUploading}
                >
                  {isUploading ? (
                    <>
                      <Loader2 size={15} className="animate-spin" /> Uploading to Shorts...
                    </>
                  ) : (
                    <>
                      <UploadCloud size={15} /> Publish to YouTube Shorts
                    </>
                  )}
                </button>
              </div>
            </form>
          )}

          {!isConnected && !isConfigured && (
            <div style={{ fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.6, padding: '10px 0' }}>
              <div style={{ fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 4 }}>
                Setup Instructions:
              </div>
              1. Go to <a href="https://console.cloud.google.com" target="_blank" rel="noreferrer" style={{ color: 'var(--text-accent)' }}>Google Cloud Console</a>.<br />
              2. Enable <strong>YouTube Data API v3</strong>.<br />
              3. Create OAuth 2.0 Credentials (Web application) with redirect URI: <code style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent-primary)' }}>http://localhost:8000/api/youtube/auth/callback</code>.<br />
              4. Paste your <strong>Client ID</strong> & <strong>Client Secret</strong> in the Studio Settings.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
