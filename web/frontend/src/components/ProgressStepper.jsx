import React from 'react';
import { Check, Loader2, Sparkles, Mic, Image, Film, FileCheck } from 'lucide-react';

const STAGES = [
  { id: 'setup', name: 'Environment & Fonts', icon: FileCheck },
  { id: 'ideation', name: 'Consensus Ideation & Script', icon: Sparkles },
  { id: 'voice', name: 'Voice Narration (edge-tts)', icon: Mic },
  { id: 'images', name: 'Beat Images Sourcing', icon: Image },
  { id: 'compositor', name: 'Compositing & Subtitles', icon: Film }
];

export default function ProgressStepper({ currentStage, percent, message, isGenerating, isComplete }) {
  if (!isGenerating && !isComplete && percent === 0) {
    return null;
  }

  const getStageIndex = (stageId) => {
    if (stageId === 'init' || stageId === 'setup') return 0;
    if (stageId === 'ideation' || stageId === 'script_ready') return 1;
    if (stageId === 'voice' || stageId === 'voice_ready') return 2;
    if (stageId === 'images' || stageId === 'gameplay') return 3;
    if (stageId === 'compositor' || stageId === 'packaging' || stageId === 'complete') return 4;
    return 0;
  };

  const activeIndex = isComplete ? STAGES.length : getStageIndex(currentStage);

  return (
    <div className="stepper-container">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>
          {isComplete ? 'Generation Complete' : 'Generation in Progress'}
        </span>
        <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-accent)', fontFamily: 'var(--font-mono)' }}>
          {percent}%
        </span>
      </div>

      <div className="progress-bar-track">
        <div className="progress-bar-fill" style={{ width: `${percent}%` }} />
      </div>

      <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 16 }}>
        {message || 'Starting pipeline...'}
      </div>

      <div className="stages-list">
        {STAGES.map((s, idx) => {
          const Icon = s.icon;
          const isCurrent = idx === activeIndex && !isComplete;
          const isDone = idx < activeIndex || isComplete;

          return (
            <div
              key={s.id}
              className={`stage-item ${isCurrent ? 'active' : ''} ${isDone ? 'completed' : ''}`}
            >
              <div className="stage-icon">
                {isDone ? (
                  <Check size={13} strokeWidth={3} />
                ) : isCurrent ? (
                  <Loader2 size={13} className="animate-spin" />
                ) : (
                  <Icon size={12} />
                )}
              </div>
              <div className="stage-info">
                <div className="stage-name">{s.name}</div>
                <div className="stage-status">
                  {isDone ? 'Completed' : isCurrent ? 'In progress...' : 'Pending'}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
