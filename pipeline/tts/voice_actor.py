"""
Voice Actor module utilizing edge-tts for high-energy neural speech and precise word-level timing.
"""

import asyncio
import re
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
    segment_text: str = ""
    lines: List[str] = Field(default_factory=list)
    active_line_index: int = 0
    active_word_index: int = 0
    active_word: str = ""

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

def segment_text_into_clauses(text: str, split_comma_threshold: int = 6) -> List[str]:
    """
    Splits text into cohesive sentences or comma-delimited clauses if long.
    - Full sentences are kept together on screen if <= split_comma_threshold words.
    - Sentences longer than split_comma_threshold with commas/semicolons are split at commas.
    - Small orphan clauses (< 3 words) are merged with adjacent clauses.
    """
    sentence_delimiters = r'(?<=[.!?])\s+'
    raw_sentences = [s.strip() for s in re.split(sentence_delimiters, text) if s.strip()]
    clauses = []
    
    for sent in raw_sentences:
        words = sent.split()
        if len(words) <= split_comma_threshold or (',' not in sent and ';' not in sent and '—' not in sent):
            clauses.append(sent)
        else:
            raw_parts = [p.strip() for p in re.split(r'[,;—]\s*', sent) if p.strip()]
            merged_parts = []
            cur = ''
            for p in raw_parts:
                if not cur:
                    cur = p
                elif len(cur.split()) < 3 or (len(cur.split()) + len(p.split())) <= split_comma_threshold:
                    cur = f"{cur}, {p}"
                else:
                    merged_parts.append(cur)
                    cur = p
            if cur:
                merged_parts.append(cur)
            # Preserve sentence ending punctuation if stripped by splitting
            if sent.endswith(('.', '!', '?')) and not merged_parts[-1].endswith(('.', '!', '?')):
                merged_parts[-1] += sent[-1]
            clauses.extend(merged_parts)
    return clauses

def wrap_clause_lines(words: List[str], max_words_per_line: int = 4) -> List[List[str]]:
    """
    Wraps a list of words into lines with at most max_words_per_line.
    """
    if not words:
        return []
    lines = []
    for i in range(0, len(words), max_words_per_line):
        lines.append(words[i : i + max_words_per_line])
    return lines

from pipeline.observability import observe

class VoiceActor:
    def __init__(self, voice: str = DEFAULT_VOICE, rate: str = DEFAULT_RATE, pitch: str = DEFAULT_PITCH):
        self.voice = voice
        self.rate = rate
        self.pitch = pitch

    @observe(name="voice_actor")
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
            pitch=self.pitch,
            boundary="WordBoundary"
        )
        
        raw_word_boundaries = []
        audio_bytes = bytearray()
        async for chunk in communicate.stream():
            chunk_type = chunk.get("type")
            if chunk_type == "audio":
                audio_bytes.extend(chunk["data"])
            elif chunk_type == "WordBoundary":
                offset_s = chunk["offset"] / 10_000_000.0
                duration_s = chunk["duration"] / 10_000_000.0
                text_part = chunk.get("text", "").strip()
                if text_part:
                    raw_word_boundaries.append((offset_s, duration_s, text_part))
                
        with open(output_audio_path, "wb") as f:
            f.write(audio_bytes)

        # Get exact audio file duration using moviepy AudioFileClip
        from moviepy.editor import AudioFileClip
        with AudioFileClip(str(output_audio_path)) as aclip:
            total_duration = aclip.duration
            
        print(f"[tts] True audio duration: {total_duration:.2f}s across {len(script_result.beats)} beats.", flush=True)

        # Normalize raw word boundaries into individual WordTiming objects
        normalized_words: List[WordTiming] = []
        for offset_s, dur_s, text_part in raw_word_boundaries:
            sub_words = text_part.split()
            if not sub_words:
                continue
            if len(sub_words) == 1:
                normalized_words.append(WordTiming(
                    word=sub_words[0],
                    start_seconds=offset_s,
                    end_seconds=offset_s + dur_s
                ))
            else:
                total_len = sum(len(w) for w in sub_words)
                cur_t = offset_s
                for idx, sw in enumerate(sub_words):
                    frac = len(sw) / max(1, total_len)
                    sw_dur = dur_s * frac
                    end_t = (offset_s + dur_s) if (idx == len(sub_words) - 1) else (cur_t + sw_dur)
                    normalized_words.append(WordTiming(
                        word=sw,
                        start_seconds=cur_t,
                        end_seconds=end_t
                    ))
                    cur_t = end_t

        # Fallback if WordBoundary wasn't emitted: proportional chunking
        if not normalized_words:
            all_words = full_text.split()
            dur_per_word = total_duration / max(1, len(all_words))
            for i, sw in enumerate(all_words):
                st = i * dur_per_word
                en = min(total_duration, (i + 1) * dur_per_word)
                normalized_words.append(WordTiming(
                    word=sw,
                    start_seconds=st,
                    end_seconds=en
                ))

        # Segment full script into cohesive sentences / comma-split clauses
        clauses = segment_text_into_clauses(full_text)
        caption_cues: List[CaptionCue] = []
        word_cursor = 0

        for clause_idx, clause in enumerate(clauses):
            clause_words = clause.split()
            if not clause_words:
                continue

            num_words = len(clause_words)
            if clause_idx == len(clauses) - 1:
                matched_words = normalized_words[word_cursor:]
            else:
                matched_words = normalized_words[word_cursor : word_cursor + num_words]
            word_cursor += len(matched_words)

            if not matched_words:
                continue

            line_word_groups = wrap_clause_lines(clause_words, max_words_per_line=4)
            clause_lines = [" ".join(grp).upper() for grp in line_word_groups]

            for w_idx in range(len(clause_words)):
                if w_idx < len(matched_words):
                    w_start = matched_words[w_idx].start_seconds
                    w_end = matched_words[w_idx].end_seconds
                else:
                    w_start = matched_words[-1].start_seconds
                    w_end = matched_words[-1].end_seconds

                if w_idx < len(clause_words) - 1 and (w_idx + 1) < len(matched_words):
                    next_start = matched_words[w_idx + 1].start_seconds
                    if next_start > w_start:
                        w_end = next_start
                elif w_idx == len(clause_words) - 1:
                    w_end = min(total_duration, max(w_end + 0.2, w_start + 0.3))

                line_idx = min(len(line_word_groups) - 1, w_idx // 4)
                word_idx_on_line = w_idx % 4

                caption_cues.append(CaptionCue(
                    text=clause_words[w_idx].upper(),
                    start_seconds=w_start,
                    end_seconds=w_end,
                    segment_text=clause.upper(),
                    lines=clause_lines,
                    active_line_index=line_idx,
                    active_word_index=word_idx_on_line,
                    active_word=clause_words[w_idx].upper()
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
            
        print(f"[tts] Generated {len(caption_cues)} speech-synchronized karaoke caption cues.", flush=True)
        return VoiceResult(
            audio_file=str(output_audio_path),
            duration_seconds=total_duration,
            words=normalized_words,
            caption_cues=caption_cues,
            beat_timings=beat_timings
        )
