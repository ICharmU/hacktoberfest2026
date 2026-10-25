import React, { useState } from 'react';
import { Sparkles, Sliders, Play, Loader2 } from 'lucide-react';

const PRESET_TOPICS = [
  "The Great Emu War",
  "Cashew Delisi Supertf",
  "Subway Surfers Origins",
  "The Tungsten Cube Craze",
  "Why Flamingos Stand on One Leg"
];

export default function TopicInput({ isGenerating, onGenerate }) {
  const [topic, setTopic] = useState('');
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [model, setModel] = useState('gemma4:12b');
  const [workerModel, setWorkerModel] = useState('gemma4:e2b');
  const [numWorkers, setNumWorkers] = useState(5);
  const [voice, setVoice] = useState('en-US-ChristopherNeural');
  const [legacy, setLegacy] = useState(false);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!topic.trim() || isGenerating) return;
    onGenerate({
      topic: topic.trim(),
      model,
      worker_model: workerModel,
      num_workers: Number(numWorkers),
      voice,
      legacy
    });
  };

  const handleSelectPreset = (preset) => {
    setTopic(preset);
  };

  return (
    <div className="studio-card">
      <div className="card-header">
        <h2 className="card-title">
          <Sparkles size={18} color="var(--accent-primary)" />
          New Slop Generation
        </h2>
        <button
          type="button"
          className="btn-icon"
          title="Toggle Advanced Parameters"
          onClick={() => setShowAdvanced(!showAdvanced)}
        >
          <Sliders size={15} />
        </button>
      </div>

      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label className="form-label">Video Topic or Prompt</label>
          <textarea
            className="topic-input-textarea"
            placeholder="e.g. The Great Emu War, Cashew Delisi, weird historical events..."
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            disabled={isGenerating}
            rows={3}
          />
        </div>

        <div className="form-group">
          <span className="form-label">Quick Topic Presets</span>
          <div className="presets-container">
            {PRESET_TOPICS.map((p) => (
              <button
                key={p}
                type="button"
                className="preset-chip"
                onClick={() => handleSelectPreset(p)}
                disabled={isGenerating}
              >
                {p}
              </button>
            ))}
          </div>
        </div>

        {showAdvanced && (
          <div style={{ background: 'var(--bg-input)', padding: 14, borderRadius: 'var(--radius-md)', marginBottom: 16, border: '1px solid var(--border-subtle)' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 10 }}>
              <div>
                <label className="form-label" style={{ fontSize: 10 }}>Lead Director Model</label>
                <input
                  type="text"
                  className="input-text"
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  disabled={isGenerating}
                />
              </div>
              <div>
                <label className="form-label" style={{ fontSize: 10 }}>Worker Model</label>
                <input
                  type="text"
                  className="input-text"
                  value={workerModel}
                  onChange={(e) => setWorkerModel(e.target.value)}
                  disabled={isGenerating}
                />
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              <div>
                <label className="form-label" style={{ fontSize: 10 }}>Number of Workers</label>
                <input
                  type="number"
                  min="1"
                  max="10"
                  className="input-text"
                  value={numWorkers}
                  onChange={(e) => setNumWorkers(e.target.value)}
                  disabled={isGenerating}
                />
              </div>
              <div>
                <label className="form-label" style={{ fontSize: 10 }}>Voice Actor (edge-tts)</label>
                <input
                  type="text"
                  className="input-text"
                  value={voice}
                  onChange={(e) => setVoice(e.target.value)}
                  disabled={isGenerating}
                />
              </div>
            </div>

            <div style={{ marginTop: 10, display: 'flex', alignItems: 'center', gap: 8 }}>
              <input
                type="checkbox"
                id="legacyMode"
                checked={legacy}
                onChange={(e) => setLegacy(e.target.checked)}
                disabled={isGenerating}
              />
              <label htmlFor="legacyMode" style={{ fontSize: 12, color: 'var(--text-secondary)', cursor: 'pointer' }}>
                Use Legacy Single-Agent Mode
              </label>
            </div>
          </div>
        )}

        <button
          type="submit"
          className="btn btn-primary btn-full"
          disabled={!topic.trim() || isGenerating}
        >
          {isGenerating ? (
            <>
              <Loader2 size={16} className="animate-spin" />
              Generating Video Slop...
            </>
          ) : (
            <>
              <Play size={16} fill="white" />
              Generate Slop Video
            </>
          )}
        </button>
      </form>
    </div>
  );
}
