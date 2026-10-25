import React, { useState, useEffect } from 'react';
import {
  Sparkles,
  Settings,
  Activity,
  Film,
  Zap,
  CheckCircle2,
  AlertCircle
} from 'lucide-react';

import SearchableVideoDropdown from './components/SearchableVideoDropdown';
import TopicInput from './components/TopicInput';
import ProgressStepper from './components/ProgressStepper';
import VideoReviewHub from './components/VideoReviewHub';
import LangfuseDrawer from './components/LangfuseDrawer';
import SettingsModal from './components/SettingsModal';

export default function App() {
  const [videos, setVideos] = useState([]);
  const [isLoadingVideos, setIsLoadingVideos] = useState(true);
  const [selectedVideoId, setSelectedVideoId] = useState(null);
  const [selectedVideoDetails, setSelectedVideoDetails] = useState(null);
  const [isLoadingDetails, setIsLoadingDetails] = useState(false);
  const [backendError, setBackendError] = useState(false);

  // Generation & SSE State
  const [isGenerating, setIsGenerating] = useState(false);
  const [currentStage, setCurrentStage] = useState('init');
  const [percent, setPercent] = useState(0);
  const [statusMessage, setStatusMessage] = useState('');
  const [isComplete, setIsComplete] = useState(false);
  const [logs, setLogs] = useState([]);

  // Drawers & Modals
  const [isDiagnosticsOpen, setIsDiagnosticsOpen] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [settings, setSettings] = useState(null);

  // Fetch initial videos and settings
  useEffect(() => {
    loadVideos();
    loadSettings();
  }, []);

  const loadVideos = async () => {
    setIsLoadingVideos(true);
    try {
      const res = await fetch('/api/videos');
      if (res.ok) {
        const data = await res.json();
        setVideos(data);
        setBackendError(false);
        // Select newest video by default if none selected
        if (data.length > 0 && !selectedVideoId) {
          selectVideo(data[0].id);
        }
      } else {
        setBackendError(true);
      }
    } catch (err) {
      console.error('Failed to load videos:', err);
      setBackendError(true);
    } finally {
      setIsLoadingVideos(false);
    }
  };

  const loadSettings = async () => {
    try {
      const res = await fetch('/api/settings');
      if (res.ok) {
        const data = await res.json();
        setSettings(data);
        setBackendError(false);
      }
    } catch (err) {
      console.error('Failed to load settings:', err);
    }
  };

  const selectVideo = async (videoId) => {
    setSelectedVideoId(videoId);
    setIsLoadingDetails(true);
    try {
      const res = await fetch(`/api/videos/${videoId}`);
      if (res.ok) {
        const data = await res.json();
        setSelectedVideoDetails(data);
      }
    } catch (err) {
      console.error(`Failed to load details for ${videoId}:`, err);
    } finally {
      setIsLoadingDetails(false);
    }
  };

  const handleGenerate = async (genOptions) => {
    setIsGenerating(true);
    setIsComplete(false);
    setPercent(5);
    setCurrentStage('init');
    setStatusMessage(`Starting slop generation for: "${genOptions.topic}"`);
    setLogs([`[system] Dispatching pipeline job for topic: "${genOptions.topic}"`]);

    try {
      const res = await fetch('/api/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(genOptions)
      });

      if (!res.ok) {
        throw new Error('Failed to start generation job');
      }

      const { job_id, stream_url } = await res.json();
      setLogs((prev) => [...prev, `[system] Job registered (${job_id}). Listening to SSE stream...`]);

      // Connect to SSE stream
      const eventSource = new EventSource(stream_url);

      eventSource.onmessage = (e) => {
        try {
          const event = JSON.parse(e.data);

          if (event.type === 'log') {
            setLogs((prev) => [...prev, event.message]);
          } else if (event.type === 'progress') {
            setCurrentStage(event.stage);
            setPercent(event.percent);
            setStatusMessage(event.message);
          } else if (event.type === 'complete') {
            setPercent(100);
            setIsComplete(true);
            setIsGenerating(false);
            setStatusMessage('Video generated successfully!');
            setLogs((prev) => [...prev, `[system] Video completed: ${event.output_id}`]);
            eventSource.close();

            // Refresh catalog and automatically display newly created video
            loadVideos().then(() => {
              if (event.output_id) {
                selectVideo(event.output_id);
              }
            });
          } else if (event.type === 'error') {
            setIsGenerating(false);
            setStatusMessage(`Error: ${event.message}`);
            setLogs((prev) => [...prev, `[error] ${event.message}`]);
            eventSource.close();
          }
        } catch (err) {
          console.error('Error parsing SSE event:', err);
        }
      };

      eventSource.onerror = (err) => {
        console.error('EventSource error:', err);
        // Don't immediately cancel if temporary disconnection
      };
    } catch (err) {
      setIsGenerating(false);
      setStatusMessage(`Failed: ${err.message}`);
      setLogs((prev) => [...prev, `[error] ${err.message}`]);
    }
  };

  const handleSaveSettings = async (newSettings) => {
    const res = await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(newSettings)
    });
    if (!res.ok) {
      throw new Error('Failed to persist settings');
    }
    await loadSettings();
  };

  return (
    <div className="app-container">
      {/* Studio Header */}
      <header className="app-header">
        <div className="brand-section">
          <div className="brand-badge">SLOP</div>
          <div>
            <span className="brand-title">Brainrot Studio</span>
            <span className="brand-subtitle">Console</span>
          </div>
        </div>

        {/* Searchable Outputs Dropdown */}
        <div className="header-center">
          <SearchableVideoDropdown
            videos={videos}
            selectedVideoId={selectedVideoId}
            onSelectVideo={selectVideo}
            isLoading={isLoadingVideos}
            onRefresh={loadVideos}
          />
        </div>

        {/* Action Controls & Status */}
        <div className="header-actions">
          <div
            className="status-pill"
            title={settings?.is_langfuse_enabled ? "Langfuse Telemetry Active" : "Langfuse Inactive (Add API keys in Settings)"}
          >
            <span className={`status-dot ${settings?.is_langfuse_enabled ? '' : 'inactive'}`} />
            <span>{settings?.is_langfuse_enabled ? 'Langfuse Active' : 'Langfuse Off'}</span>
          </div>

          <button
            type="button"
            className="btn btn-secondary"
            style={{ fontSize: 12, padding: '7px 12px' }}
            onClick={() => setIsDiagnosticsOpen(!isDiagnosticsOpen)}
          >
            <Activity size={14} color="var(--accent-primary)" />
            Diagnostics / Logs
          </button>

          <button
            type="button"
            className="btn-icon"
            title="Settings & Persistent API Keys"
            onClick={() => setIsSettingsOpen(true)}
          >
            <Settings size={16} />
          </button>
        </div>
      </header>

      {backendError && (
        <div style={{ background: '#450a0a', borderBottom: '1px solid #7f1d1d', color: '#fecaca', padding: '8px 24px', fontSize: 13, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <AlertCircle size={16} color="#f87171" />
            <span><strong>Backend Server Offline:</strong> Cannot reach Python backend on port 8000. Run <code style={{ background: '#1c1917', color: '#60a5fa', padding: '2px 6px', borderRadius: 4, fontFamily: 'var(--font-mono)' }}>pixi run ui-server</code> in your project root to connect.</span>
          </div>
          <button type="button" className="btn btn-secondary" style={{ padding: '4px 10px', fontSize: 11 }} onClick={loadVideos}>
            Retry Connection
          </button>
        </div>
      )}

      {/* Main Studio Body */}
      <main className="main-content">
        {/* Left Column: Generation Console & Live Stepper */}
        <div>
          <TopicInput
            isGenerating={isGenerating}
            onGenerate={handleGenerate}
          />

          <ProgressStepper
            currentStage={currentStage}
            percent={percent}
            message={statusMessage}
            isGenerating={isGenerating}
            isComplete={isComplete}
          />
        </div>

        {/* Right Column: Publication Hub & Video Review */}
        <div>
          <VideoReviewHub
            video={selectedVideoDetails}
            isLoadingDetails={isLoadingDetails}
          />
        </div>
      </main>

      {/* Slide-out Diagnostics & Langfuse Drawer */}
      <LangfuseDrawer
        isOpen={isDiagnosticsOpen}
        onClose={() => setIsDiagnosticsOpen(false)}
        logs={logs}
        settings={settings}
        onClearLogs={() => setLogs([])}
      />

      {/* Persistent Settings Modal */}
      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        settings={settings}
        onSaveSettings={handleSaveSettings}
      />
    </div>
  );
}
