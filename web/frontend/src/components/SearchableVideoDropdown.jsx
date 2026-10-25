import React, { useState, useEffect, useRef } from 'react';
import { Search, Film, Clock, X, ChevronDown, Check, RefreshCw } from 'lucide-react';

export default function SearchableVideoDropdown({ videos, selectedVideoId, onSelectVideo, isLoading, onRefresh }) {
  const [isOpen, setIsOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const wrapperRef = useRef(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event) {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Simple string matching against title, topic, tags, and folder name (id)
  const filteredVideos = (videos || []).filter((v) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase().trim();
    const matchTitle = (v.title || '').toLowerCase().includes(q);
    const matchTopic = (v.topic || '').toLowerCase().includes(q);
    const matchId = (v.id || '').toLowerCase().includes(q);
    const matchTags = (v.tags || []).some((t) => t.toLowerCase().includes(q));
    return matchTitle || matchTopic || matchId || matchTags;
  });

  const selectedVideo = (videos || []).find((v) => v.id === selectedVideoId);

  const handleSelect = (video) => {
    onSelectVideo(video.id);
    setIsOpen(false);
  };

  const formatDuration = (seconds) => {
    if (!seconds) return '0:00';
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s < 10 ? '0' : ''}${s}`;
  };

  const formatDate = (isoString) => {
    if (!isoString) return '';
    try {
      const d = new Date(isoString);
      return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
    } catch {
      return isoString;
    }
  };

  return (
    <div className="search-dropdown-wrapper" ref={wrapperRef}>
      <div
        className="search-input-box"
        onClick={() => setIsOpen(true)}
        style={{ cursor: 'pointer' }}
      >
        <Search size={15} color="var(--text-muted)" />
        <input
          type="text"
          placeholder={selectedVideo ? `Active: ${selectedVideo.title}` : `Select video from /outputs (${videos?.length || 0} available)...`}
          value={searchQuery}
          onChange={(e) => {
            setSearchQuery(e.target.value);
            setIsOpen(true);
          }}
          onFocus={() => setIsOpen(true)}
          style={{ cursor: 'text' }}
        />

        {videos && videos.length > 0 && (
          <span className="meta-pill" style={{ fontSize: 10, padding: '2px 6px', whiteSpace: 'nowrap' }}>
            {videos.length} videos
          </span>
        )}

        {searchQuery ? (
          <button
            type="button"
            className="btn-icon"
            style={{ padding: 2, background: 'transparent', border: 'none' }}
            onClick={(e) => {
              e.stopPropagation();
              setSearchQuery('');
            }}
          >
            <X size={14} color="var(--text-muted)" />
          </button>
        ) : (
          <button
            type="button"
            className="btn-icon"
            style={{ padding: 2, background: 'transparent', border: 'none' }}
            onClick={(e) => {
              e.stopPropagation();
              setIsOpen(!isOpen);
            }}
          >
            <ChevronDown size={14} color="var(--text-muted)" />
          </button>
        )}
      </div>

      {isOpen && (
        <div className="dropdown-menu">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '6px 10px', borderBottom: '1px solid var(--border-subtle)', marginBottom: 4 }}>
            <span style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-muted)' }}>
              Outputs Video Catalog ({filteredVideos.length})
            </span>
            {onRefresh && (
              <button
                type="button"
                className="btn-icon"
                style={{ padding: 3 }}
                title="Refresh videos from /outputs"
                onClick={(e) => {
                  e.stopPropagation();
                  onRefresh();
                }}
              >
                <RefreshCw size={12} className={isLoading ? "animate-spin" : ""} />
              </button>
            )}
          </div>

          {isLoading ? (
            <div className="dropdown-empty">Loading video catalog...</div>
          ) : !videos || videos.length === 0 ? (
            <div className="dropdown-empty" style={{ display: 'flex', flexDirection: 'column', gap: 6, alignItems: 'center' }}>
              <span>No videos found in /outputs folder yet.</span>
              <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Generate your first slop video using the left panel!</span>
            </div>
          ) : filteredVideos.length === 0 ? (
            <div className="dropdown-empty">
              No videos matching "{searchQuery}"
            </div>
          ) : (
            filteredVideos.map((video) => {
              const isSelected = video.id === selectedVideoId;
              return (
                <div
                  key={video.id}
                  className={`dropdown-item ${isSelected ? 'active' : ''}`}
                  onClick={() => handleSelect(video)}
                >
                  <div className="dropdown-item-title">
                    <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <Film size={13} color={isSelected ? "var(--accent-primary)" : "var(--text-muted)"} />
                      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 360 }}>
                        {video.title}
                      </span>
                    </span>
                    {isSelected && <Check size={14} color="var(--accent-success)" />}
                  </div>

                  <div className="dropdown-item-meta">
                    {video.topic && <span className="meta-pill">{video.topic}</span>}
                    <span style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
                      <Clock size={11} /> {formatDuration(video.duration_seconds)}
                    </span>
                    <span>{formatDate(video.created_at)}</span>
                    <span style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>{video.id}</span>
                  </div>
                </div>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}
