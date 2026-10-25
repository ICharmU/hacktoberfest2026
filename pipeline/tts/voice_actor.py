"""
Voice Actor module utilizing edge-tts for high-energy neural speech and precise word-level timing.
"""

import asyncio
from pathlib import Path
from typing import List
from pydantic import BaseModel, Field
import edge_tts

from pipeline.config import DEFAULT_VOICE, DEFAULT_RATE, DEFAULT_PITCH
from pipeline.writer.script_writer import ScriptResult

class WordTiming(BaseModel):
    word: str
    start_seconds: float
    end_seconds: float

class CaptionCue(BaseModel):
    text: str
    start_seconds: float
    end_seconds: float

class BeatTiming(BaseModel):
    beat_index: int
    text: str
    caption_lines: List[str]
    image_query: str
    start_seconds: float
    end_seconds: float

class VoiceResult(BaseModel):
    audio_file: str
    duration_seconds: float
    words: List[WordTiming] = Field(default_factory=list)
    caption_cues: List[CaptionCue] = Field(default_factory=list)
    beat_timings: List[BeatTiming] = Field(default_factory=list)

class VoiceActor:
    def __init__(self, voice: str = DEFAULT_VOICE, rate: str = DEFAULT_RATE, pitch: str = DEFAULT_PITCH):
        self.voice = voice
        self.rate = rate
        self.pitch = pitch

    def synthesize(self, script_result: ScriptResult, output_audio_path: Path) -> VoiceResult:
        """
        Synchronously wraps async edge-tts generation.
        """
        return asyncio.run(self._synthesize_async(script_result, output_audio_path))

    async def _synthesize_async(self, script_result: ScriptResult, output_audio_path: Path) -> VoiceResult:
        output_audio_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"[tts] Generating speech with voice '{self.voice}' (rate={self.rate})...", flush=True)
        
        full_text = " ".join([b.text for b in script_result.beats])
        communicate = edge_tts.Communicate(
            text=full_text,
            voice=self.voice,
            rate=self.rate,
            pitch=self.pitch
        )
        
        sentence_boundaries = []
        audio_bytes = bytearray()
        async for chunk in communicate.stream():
            chunk_type = chunk.get("type")
            if chunk_type == "audio":
                audio_bytes.extend(chunk["data"])
            elif chunk_type == "SentenceBoundary":
                offset_s = chunk["offset"] / 10_000_000.0
                duration_s = chunk["duration"] / 10_000_000.0
                text_part = chunk.get("text", "").strip()
                if text_part:
                    sentence_boundaries.append((offset_s, duration_s, text_part))
                
        with open(output_audio_path, "wb") as f:
            f.write(audio_bytes)

        # Get exact audio file duration using moviepy AudioFileClip
        from moviepy.editor import AudioFileClip
        with AudioFileClip(str(output_audio_path)) as aclip:
            total_duration = aclip.duration
            
        print(f"[tts] True audio duration: {total_duration:.2f}s across {len(script_result.beats)} beats.", flush=True)

        # Generate verbatim rapid-fire caption cues (1-3 words each) for maximum overstimulation
        caption_cues: List[CaptionCue] = []
        
        if sentence_boundaries:
            for s_start, s_dur, s_text in sentence_boundaries:
                words = s_text.split()
                if not words:
                    continue
                # Split words into rapid chunks of 1 to 2 words (occasionally 3 if short)
                word_chunks = []
                idx = 0
                while idx < len(words):
                    take = 2
                    if idx + 2 >= len(words) and (len(words) - idx) == 3:
                        take = 3
                    elif idx + take > len(words):
                        take = len(words) - idx
                    word_chunks.append(" ".join(words[idx : idx + take]))
                    idx += take
                
                # Proportional duration for each chunk based on character length
                total_chars = sum(len(c) for c in word_chunks)
                chunk_cursor = s_start
                for c_idx, chunk_str in enumerate(word_chunks):
                    char_ratio = len(chunk_str) / max(1, total_chars)
                    chunk_duration = s_dur * char_ratio
                    c_end = min(total_duration, chunk_cursor + chunk_duration)
                    if c_idx == len(word_chunks) - 1:
                        c_end = min(total_duration, s_start + s_dur)
                    
                    caption_cues.append(CaptionCue(
                        text=chunk_str.upper(),
                        start_seconds=chunk_cursor,
                        end_seconds=max(chunk_cursor + 0.15, c_end)
                    ))
                    chunk_cursor = c_end
        else:
            # Fallback if sentence boundaries weren't returned: chunk full script across duration
            all_words = full_text.split()
            chunk_size = 2
            word_chunks = [" ".join(all_words[i:i+chunk_size]) for i in range(0, len(all_words), chunk_size)]
            dur_per_chunk = total_duration / max(1, len(word_chunks))
            for i, chunk_str in enumerate(word_chunks):
                st = i * dur_per_chunk
                en = min(total_duration, (i + 1) * dur_per_chunk)
                caption_cues.append(CaptionCue(
                    text=chunk_str.upper(),
                    start_seconds=st,
                    end_seconds=en
                ))

        # Segment total duration across the script beats for image display
        beat_timings: List[BeatTiming] = []
        words_per_beat = [max(1, len(b.text.split())) for b in script_result.beats]
        total_words = sum(words_per_beat)
        
        current_time = 0.0
        for i, beat in enumerate(script_result.beats):
            beat_word_count = words_per_beat[i]
            fraction = beat_word_count / total_words
            beat_duration = total_duration * fraction
            start_t = current_time
            end_t = total_duration if (i == len(script_result.beats) - 1) else (current_time + beat_duration)
            current_time = end_t
            
            beat_timings.append(BeatTiming(
                beat_index=i,
                text=beat.text,
                caption_lines=beat.caption_lines,
                image_query=beat.image_search_query,
                start_seconds=start_t,
                end_seconds=end_t
            ))
            
        print(f"[tts] Generated {len(caption_cues)} verbatim rapid-fire caption cues.", flush=True)
        return VoiceResult(
            audio_file=str(output_audio_path),
            duration_seconds=total_duration,
            words=[],
            caption_cues=caption_cues,
            beat_timings=beat_timings
        )
