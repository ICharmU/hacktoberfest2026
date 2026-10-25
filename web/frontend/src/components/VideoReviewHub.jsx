import React, { useState } from 'react';
import { Download, Copy, Check, Film, Clock, Tag, ListOrdered, Share2, Youtube, ExternalLink } from 'lucide-react';

export default function VideoReviewHub({ video, isLoadingDetails, onOpenYouTubeUpload }) {
  const [copiedKey, setCopiedKey] = useState(null);

  const copyToClipboard = (text, key) => {
    if (!text) return;
    navigator.clipboard.writeText(text);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 2000);
  };

  const formatSeconds = (sec) => {
    if (sec === undefined || sec === null) return '0:00';
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${m}:${s < 10 ? '0' : ''}${s}`;
  };

  if (!video) {
    return (
      <div className="studio-card">
        <div className="card-header">
          <h2 className="card-title">
            <Film size={18} color="var(--accent-primary)" />
            Publication Review Hub
          </h2>
        </div>
        <div className="video-empty-placeholder" style={{ height: 420 }}>
          <Film size={48} strokeWidth={1.5} color="var(--border-subtle)" />
          <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-secondary)' }}>
            No Video Selected
          </div>
          <div style={{ fontSize: 13, color: 'var(--text-muted)', maxWidth: 360 }}>
            Generate a new slop video using the left console or select any previously rendered video from the search dropdown above.
          </div>
        </div>
      </div>
    );
  }

  const meta = video.metadata || {};
  const tagsText = (video.tags || []).map((t) => (t.startsWith('#') ? t : `#${t}`)).join(' ');
  const beats = meta.beats || [];

  return (
    <div className="studio-card">
      <div className="card-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <h2 className="card-title">
            <Film size={18} color="var(--accent-primary)" />
            Publication Review Hub
          </h2>
          <span className="status-pill" style={{ borderColor: 'rgba(16, 185, 129, 0.4)', color: 'var(--accent-success)' }}>
            <span className="status-dot" /> Ready for Publication
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {meta.youtube_shorts_url ? (
            <a
              href={meta.youtube_shorts_url}
              target="_blank"
              rel="noreferrer"
              className="btn btn-secondary"
              style={{ color: '#ef4444', textDecoration: 'none', borderColor: '#ef4444' }}
            >
              <Youtube size={14} /> View Shorts
            </a>
          ) : (
            <button
              type="button"
              className="btn btn-primary"
              style={{ background: '#ef4444', borderColor: '#ef4444' }}
              onClick={onOpenYouTubeUpload}
            >
              <Youtube size={15} /> Upload to YouTube
            </button>
          )}

          <a
            href={video.download_url || `/api/videos/${video.id}/download`}
            download
            className="btn btn-secondary"
            style={{ textDecoration: 'none' }}
          >
            <Download size={14} /> Download MP4
          </a>
        </div>
      </div>

      <div className="publication-hub">
        {/* 9:16 Vertical Video Player */}
        <div>
          <div className="video-player-card">
            <video
              key={video.id}
              className="video-element"
              controls
              autoPlay={false}
              playsInline
              preload="metadata"
              src={video.stream_url || `/api/videos/${video.id}/stream`}
            >
              Your browser does not support the video tag.
            </video>
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 10, fontSize: 12, color: 'var(--text-muted)' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <Clock size={12} /> {formatSeconds(video.duration_seconds)}
            </span>
            <span>ID: {video.id}</span>
          </div>
        </div>

        {/* Publication Metadata & Copy Box */}
        <div className="publication-details">
          {/* Title Box */}
          <div className="meta-field-group">
            <div className="meta-field-header">
              <span className="meta-field-label">Video Title</span>
              <button
                type="button"
                className="btn-icon"
                style={{ padding: '3px 8px', fontSize: 11, display: 'flex', alignItems: 'center', gap: 4 }}
                onClick={() => copyToClipboard(video.title, 'title')}
              >
                {copiedKey === 'title' ? (
                  <>
                    <Check size={11} color="var(--accent-success)" /> Copied
                  </>
                ) : (
                  <>
                    <Copy size={11} /> Copy Title
                  </>
                )}
              </button>
            </div>
            <div className="meta-field-content" style={{ fontWeight: 700, fontSize: 15 }}>
              {video.title}
            </div>
          </div>

          {/* Description Box */}
          <div className="meta-field-group">
            <div className="meta-field-header">
              <span className="meta-field-label">Description & Caption</span>
              <button
                type="button"
                className="btn-icon"
                style={{ padding: '3px 8px', fontSize: 11, display: 'flex', alignItems: 'center', gap: 4 }}
                onClick={() => copyToClipboard(video.description || `${video.title} ${tagsText}`, 'desc')}
              >
                {copiedKey === 'desc' ? (
                  <>
                    <Check size={11} color="var(--accent-success)" /> Copied
                  </>
                ) : (
                  <>
                    <Copy size={11} /> Copy Description
                  </>
                )}
              </button>
            </div>
            <div className="meta-field-content">
              {video.description || <span style={{ color: 'var(--text-muted)' }}>No description generated.</span>}
            </div>
          </div>

          {/* Tags Box */}
          <div className="meta-field-group">
            <div className="meta-field-header">
              <span className="meta-field-label" style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                <Tag size={11} /> Hashtags ({video.tags?.length || 0})
              </span>
              <button
                type="button"
                className="btn-icon"
                style={{ padding: '3px 8px', fontSize: 11, display: 'flex', alignItems: 'center', gap: 4 }}
                onClick={() => copyToClipboard(tagsText, 'tags')}
              >
                {copiedKey === 'tags' ? (
                  <>
                    <Check size={11} color="var(--accent-success)" /> Copied
                  </>
                ) : (
                  <>
                    <Copy size={11} /> Copy Tags
                  </>
                )}
              </button>
            </div>
            <div className="tags-pills-row">
              {video.tags && video.tags.length > 0 ? (
                video.tags.map((t, idx) => (
                  <span key={idx} className="tag-badge">
                    {t.startsWith('#') ? t : `#${t}`}
                  </span>
                ))
              ) : (
                <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>No tags specified</span>
              )}
            </div>
          </div>

          {/* Script Beats Breakdown */}
          {beats.length > 0 && (
            <div className="meta-field-group">
              <div className="meta-field-header">
                <span className="meta-field-label" style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                  <ListOrdered size={11} /> Script Beats Timeline ({beats.length})
                </span>
                <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Subtitles & Timings</span>
              </div>
              <div className="beats-timeline">
                {beats.map((b, idx) => (
                  <div key={idx} className="beat-row">
                    <span className="beat-time">
                      {formatSeconds(b.start_seconds)} - {formatSeconds(b.end_seconds)}
                    </span>
                    <div style={{ flex: 1 }}>
                      <div className="beat-text">{b.text}</div>
                      {b.image_query && (
                        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
                          Image: <span style={{ color: 'var(--text-secondary)' }}>{b.image_query}</span>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
