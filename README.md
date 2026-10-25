# Brainrot Slop Video Generation Pipeline

An automated short-form video generation pipeline designed to create high-retention, pseudo-informative "brainrot" vertical videos (1080x1920) from topic/date queries.

## Features
- **Researcher Agent**: Pulls contextual historical facts and events via DuckDuckGo (`ddgs`).
- **Narrative Script Writer**: Prompts local Ollama (`gemma4:12b`) for cohesive storytelling, topic framing, comparative transitions, and unhinged ending takeaways.
- **Voice Actor (`edge-tts`)**: Synthesizes speech with neural voice profiles (`en-US-ChristopherNeural` / `en-US-GuyNeural`) tuned for fast-paced pacing.
- **Verbatim Rapid-Fire Subtitles**: 100% verbatim speech display synchronized in rapid 1–2 word cues with Anton bold typography.
- **Visual Assets**: Downloads relevant web images for each beat, framed with borders and flashing red/yellow pointing arrows.
- **Subway Surfers Background**: Automatically slices random continuous segments from `assets/gameplay/subway_surfers.mp4`.
- **Langfuse Telemetry**: Full end-to-end tracing for LLM generations, searches, voice synthesis, and video renders.

---

## Quickstart

### 1. Launch Web UI Studio (React + FastAPI)
Run the built-in web studio for a clean, visual console with real-time video progress, publication review, searchable output browsing, and Langfuse diagnostics:

```bash
pixi run ui-server
```
Then open [http://localhost:8000](http://localhost:8000) in your browser.

### 2. CLI Generation
```bash
# Default run
pixi run generate

# Specify topic or date
pixi run generate --topic "July 20, 1969"

# Customize voice and speed
pixi run generate --topic "Ancient Rome" --voice "en-US-GuyNeural" --rate "+22%"
```

### 2. Langfuse Observability Setup
Create a `.env` file in the project root with your Langfuse API keys (from [cloud.langfuse.com](https://cloud.langfuse.com) or [us.cloud.langfuse.com](https://us.cloud.langfuse.com)):

```env
LANGFUSE_PUBLIC_KEY="pk-lf-..."
LANGFUSE_SECRET_KEY="sk-lf-..."
LANGFUSE_HOST="https://cloud.langfuse.com" # or "https://us.cloud.langfuse.com"
```

*Note: If no keys are provided, the pipeline runs smoothly in local mode with telemetry disabled.*

---

## Project Structure
```text
├── assets/
│   ├── gameplay/        # subway_surfers.mp4 source
│   ├── fonts/           # Anton.ttf viral caption font
│   └── styles/          # caption_styles.json, voice_options.json
├── pipeline/
│   ├── researcher/      # BaseResearcher, DateResearcher
│   ├── writer/          # ScriptWriter with narrative prompts
│   ├── tts/             # VoiceActor (edge-tts + verbatim timing)
│   ├── assets/          # ImageFetcher (ddgs), GameplayManager
│   ├── compositor/      # VideoCompositor (flashing arrows, overlays)
│   ├── observability/   # Langfuse tracer and @observe integration
│   └── main.py          # CLI orchestrator
└── outputs/             # Timestamped runs (video.mp4, metadata.json)
```
