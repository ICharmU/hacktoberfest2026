"""
Main entry point for the Automated Brainrot Slop Video Generation Pipeline.

Usage:
    python -m pipeline.main --topic "October 25, 2026"
    python -m pipeline.main --date "July 20, 1969"
"""

import argparse
import datetime
import json
from pathlib import Path
import sys

# Fix MoviePy 1.0.3 compatibility with Pillow 10+
import PIL.Image
if not hasattr(PIL.Image, "ANTIALIAS"):
    PIL.Image.ANTIALIAS = PIL.Image.Resampling.LANCZOS

# Ensure UTF-8 output on Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from pipeline.observability import observe, init_observability, flush_telemetry
from pipeline.config import (
    DEFAULT_MODEL,
    DEFAULT_VOICE,
    DEFAULT_RATE,
    DEFAULT_PITCH,
    OUTPUTS_DIR,
    DEFAULT_GAMEPLAY_VIDEO,
    DEFAULT_FONT_FILE
)
from assets.download_assets import ensure_fonts
from pipeline.researcher.date_researcher import DateResearcher
from pipeline.writer.script_writer import ScriptWriter, ScriptResult
from pipeline.harness import IdeationHarness
from pipeline.tts.voice_actor import VoiceActor
from pipeline.assets.image_fetcher import ImageFetcher
from pipeline.assets.gameplay_manager import GameplayManager
from pipeline.compositor.renderer import VideoCompositor

@observe(name="brainrot_video_pipeline")
def run_pipeline(
    topic: str,
    model: str = DEFAULT_MODEL,
    worker_model: str = "gemma4:e2b",
    num_workers: int = 5,
    voice: str = DEFAULT_VOICE,
    rate: str = DEFAULT_RATE,
    pitch: str = DEFAULT_PITCH,
    legacy: bool = False
) -> Path:
    init_observability()
    print("=" * 60)
    print(f"Starting Brainrot Slop Pipeline for topic: '{topic}'")
    print("=" * 60)

    # 1. Ensure required fonts/styles are present
    ensure_fonts()

    # 2. Prepare timestamped output folder
    timestamp_str = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    run_dir = OUTPUTS_DIR / timestamp_str
    run_dir.mkdir(parents=True, exist_ok=True)
    temp_dir = run_dir / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    print(f"[pipeline] Output directory: {run_dir}")

    # 3. Ideation: Harness vs Legacy
    harness_output = None
    if not legacy:
        harness = IdeationHarness(
            worker_model=worker_model,
            director_model=model,
            num_workers=num_workers
        )
        harness_output = harness.run(topic)
        script_result = ScriptResult(
            title=harness_output.title,
            description=harness_output.description,
            tags=harness_output.tags,
            beats=harness_output.beats,
            full_script=harness_output.full_script
        )
    else:
        print("[pipeline] Running in legacy single-agent research mode...", flush=True)
        researcher = DateResearcher(max_results=8)
        research_result = researcher.research(topic)
        writer = ScriptWriter(model=model)
        script_result = writer.write_script(research_result)

    print(f"\n[pipeline] Final Video Title: {script_result.title}")
    print(f"[pipeline] Number of beats: {len(script_result.beats)}")
    for idx, beat in enumerate(script_result.beats, 1):
        print(f"  Beat {idx}: {beat.text}")
        print(f"    Image query: {beat.image_search_query}")

    # 4. Voice Actor (edge-tts)
    tts_audio_path = temp_dir / "narration.mp3"
    voice_actor = VoiceActor(voice=voice, rate=rate, pitch=pitch)
    voice_result = voice_actor.synthesize(script_result, tts_audio_path)

    # 5. Asset Sourcing: Images for each beat
    image_fetcher = ImageFetcher()
    beat_images = []
    for i, beat in enumerate(voice_result.beat_timings):
        img_path = temp_dir / f"beat_{i}.png"
        image_fetcher.fetch_image(beat.image_query, img_path)
        beat_images.append(img_path)

    # 6. Asset Sourcing: Subway Surfers Gameplay background
    gameplay_mgr = GameplayManager(DEFAULT_GAMEPLAY_VIDEO)
    sliced_gameplay = gameplay_mgr.get_sliced_clip(voice_result.duration_seconds)

    # 7. Video Compositor (Flashing arrows, vertical layout, bold subtitles)
    final_video_path = run_dir / "video.mp4"
    compositor = VideoCompositor(font_path=DEFAULT_FONT_FILE)
    compositor.compose(
        gameplay_clip=sliced_gameplay,
        voice_result=voice_result,
        beat_images=beat_images,
        output_video_path=final_video_path
    )

    # 8. Packaging Metadata JSON
    metadata = {
        "title": script_result.title,
        "description": script_result.description,
        "tags": script_result.tags,
        "topic": topic,
        "created_at": datetime.datetime.now().isoformat(),
        "duration_seconds": round(voice_result.duration_seconds, 2),
        "voice": voice,
        "director_model": model,
        "worker_model": worker_model if not legacy else None,
        "beats": [
            {
                "index": b.beat_index,
                "text": b.text,
                "caption_lines": b.caption_lines,
                "image_query": b.image_query,
                "start_seconds": round(b.start_seconds, 2),
                "end_seconds": round(b.end_seconds, 2)
            }
            for b in voice_result.beat_timings
        ],
        "video_file": "video.mp4"
    }

    if harness_output:
        metadata["selected_archetype"] = harness_output.selected_archetype
        metadata["archetype_justification"] = harness_output.archetype_justification
        metadata["hook"] = harness_output.hook.model_dump()
        metadata["outline"] = harness_output.outline.model_dump()
        metadata["consensus_facts"] = harness_output.consensus_facts
        metadata["harness_stats"] = harness_output.metadata

    metadata_path = run_dir / "metadata.json"
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    print("\n" + "=" * 60)
    print(f"PIPELINE COMPLETED SUCCESSFULLY!")
    print(f"Video MP4: {final_video_path}")
    print(f"Metadata:  {metadata_path}")
    print("=" * 60)

    flush_telemetry()
    return run_dir

def main():
    parser = argparse.ArgumentParser(description="Automated Brainrot Slop Video Generator with Consensus Ideation Harness")
    parser.add_argument("--topic", type=str, default="October 25, 2026", help="Target topic, historical date, URL, or local file")
    parser.add_argument("--date", type=str, default=None, help="Alias for --topic")
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL, help="Lead Director Ollama model (default: gemma4:12b)")
    parser.add_argument("--worker-model", type=str, default="gemma4:e2b", help="Worker Ollama model (default: gemma4:e2b)")
    parser.add_argument("--workers", type=int, default=5, help="Number of worker subagents to dispatch (default: 5)")
    parser.add_argument("--voice", type=str, default=DEFAULT_VOICE, help="edge-tts voice identifier")
    parser.add_argument("--rate", type=str, default=DEFAULT_RATE, help="Speech rate adjustment (e.g. +18%%)")
    parser.add_argument("--pitch", type=str, default=DEFAULT_PITCH, help="Speech pitch adjustment")
    parser.add_argument("--legacy", action="store_true", help="Use legacy single-agent researcher instead of consensus harness")

    args = parser.parse_args()
    target_topic = args.date if args.date else args.topic
    run_pipeline(
        topic=target_topic,
        model=args.model,
        worker_model=args.worker_model,
        num_workers=args.workers,
        voice=args.voice,
        rate=args.rate,
        pitch=args.pitch,
        legacy=args.legacy
    )

if __name__ == "__main__":
    main()
