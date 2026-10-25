"""
Voice Actor module utilizing edge-tts for high-energy neural speech and precise word-level timing.
"""

import asyncio
import re
from pathlib import Path
from typing import List
from pydantic import BaseModel, Field
import edge_tts

from pipeline.config import DEFAULT_VOICE, DEFAULT_RATE, DEFAULT_PITCH, DEFAULT_FONT_FILE, load_caption_style
from pipeline.writer.script_writer import ScriptResult
from PIL import ImageFont

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

def get_caption_font() -> ImageFont.ImageFont:
    """Loads the viral caption font at the styled font size."""
    style = load_caption_style("brainrot_viral")
    font_size = style.get("font_size", 86)
    try:
        return ImageFont.truetype(str(DEFAULT_FONT_FILE), font_size)
    except Exception:
        return ImageFont.load_default()

def measure_line_width(words: List[str], font: ImageFont.ImageFont = None) -> float:
    """Measures exact pixel width of a list of words rendered with the specified font."""
    if not words:
        return 0.0
    text = " ".join(words).upper()
    if font and hasattr(font, "getlength"):
        return font.getlength(text)
    return len(text) * 40.0

def balance_words_into_lines(
    words: List[str],
    font: ImageFont.ImageFont = None,
    max_lines: int = 3,
    max_width: float = 800.0
) -> List[List[str]]:
    """
    Partitions words into 1, 2, or at most max_lines (default 3) lines such that:
    1. Every line width is <= max_width (measured with actual font character metrics).
    2. The line widths are balanced to be as equal as possible across lines.
    3. Prefers 2 lines over 3 lines whenever 2 lines fit under max_width.
    """
    n = len(words)
    if n == 0:
        return []
    if n == 1:
        return [[words[0]]]

    # Try 1 line if short
    w_all = measure_line_width(words, font)
    if w_all <= max_width and n <= 4:
        return [words]

    best_partition = None
    best_score = float('inf')

    if w_all <= max_width:
        best_partition = [words]
        best_score = w_all * 0.1

    # Try 2 lines
    for i in range(1, n):
        l1 = words[:i]
        l2 = words[i:]
        w1 = measure_line_width(l1, font)
        w2 = measure_line_width(l2, font)
        if w1 <= max_width and w2 <= max_width:
            diff = abs(w1 - w2)
            orphan_penalty = 200.0 if (len(l1) == 1 or len(l2) == 1) else 0.0
            score = diff + orphan_penalty
            if score < best_score:
                best_score = score
                best_partition = [l1, l2]

    # Try 3 lines if max_lines >= 3 and 2 lines couldn't fit
    if max_lines >= 3 and best_partition is None:
        for i in range(1, n - 1):
            for j in range(i + 1, n):
                l1 = words[:i]
                l2 = words[i:j]
                l3 = words[j:]
                w1 = measure_line_width(l1, font)
                w2 = measure_line_width(l2, font)
                w3 = measure_line_width(l3, font)
                if w1 <= max_width and w2 <= max_width and w3 <= max_width:
                    diff = max(w1, w2, w3) - min(w1, w2, w3)
                    orphan_penalty = 300.0 if (len(l1) == 1 or len(l2) == 1 or len(l3) == 1) else 0.0
                    score = diff + orphan_penalty
                    if score < best_score:
                        best_score = score
                        best_partition = [l1, l2, l3]

    if best_partition:
        return best_partition

    # Fallback greedy wrapping
    lines = []
    cur_line = []
    for w in words:
        test_line = cur_line + [w]
        if measure_line_width(test_line, font) <= max_width:
            cur_line = test_line
        else:
            if cur_line:
                lines.append(cur_line)
            cur_line = [w]
    if cur_line:
        lines.append(cur_line)
    return lines[:max_lines]

def paginate_word_timings(
    word_timings: List[WordTiming],
    font: ImageFont.ImageFont = None,
    min_words_per_page: int = 4,
    max_words_per_page: int = 9,
    max_lines: int = 3,
    max_width: float = 800.0
) -> List[List[List[WordTiming]]]:
    """
    Paginates a sequence of WordTiming objects into multi-line pages:
    - Each page has between min_words_per_page (e.g. 4) and max_words_per_page words.
    - Each page has at most max_lines (3 lines maximum).
    - Calculates character width before placing each line (<= max_width).
    - Advances to the next page when full even if mid-sentence.
    - Balances width across lines so text does not spill outside borders.
    Returns: List of pages, where each page is a List of lines, and each line is a List of WordTiming.
    """
    pages = []
    idx = 0
    total = len(word_timings)
    
    while idx < total:
        remaining = total - idx
        best_count = min(min_words_per_page, remaining)
        
        for count in range(best_count, min(max_words_per_page + 1, remaining + 1)):
            cand_words = [wt.word for wt in word_timings[idx : idx + count]]
            lines = balance_words_into_lines(cand_words, font=font, max_lines=max_lines, max_width=max_width)
            if len(lines) <= max_lines and all(measure_line_width(l, font) <= max_width for l in lines):
                best_count = count
            else:
                break
                
        # Remnant handling: avoid leaving an orphan with < min_words_per_page
        rem_after = remaining - best_count
        if 0 < rem_after < min_words_per_page:
            cand_all = [wt.word for wt in word_timings[idx : idx + best_count + rem_after]]
            lines_all = balance_words_into_lines(cand_all, font=font, max_lines=max_lines, max_width=max_width)
            if len(lines_all) <= max_lines and all(measure_line_width(l, font) <= max_width for l in lines_all):
                best_count += rem_after
            else:
                half = (best_count + rem_after) // 2
                best_count = max(min_words_per_page, half)

        # Slice the WordTiming objects for this page
        page_wt = word_timings[idx : idx + best_count]
        page_words_str = [wt.word for wt in page_wt]
        page_str_lines = balance_words_into_lines(page_words_str, font=font, max_lines=max_lines, max_width=max_width)
        
        # Map WordTiming objects to the balanced lines
        page_lines_wt = []
        wt_cursor = 0
        for str_line in page_str_lines:
            line_wt = page_wt[wt_cursor : wt_cursor + len(str_line)]
            page_lines_wt.append(line_wt)
            wt_cursor += len(str_line)
            
        pages.append(page_lines_wt)
        idx += best_count
        
    return pages

def segment_text_into_clauses(text: str, split_comma_threshold: int = 6) -> List[str]:
    """
    Legacy helper: Splits text into cohesive sentences or comma-delimited clauses.
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
            if sent.endswith(('.', '!', '?')) and not merged_parts[-1].endswith(('.', '!', '?')):
                merged_parts[-1] += sent[-1]
            clauses.extend(merged_parts)
    return clauses

def wrap_clause_lines(words: List[str], max_words_per_line: int = 4) -> List[List[str]]:
    """
    Wraps a list of words into balanced lines using font width metrics when available.
    """
    return balance_words_into_lines(words, max_lines=3, max_width=800.0)

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

        # Paginate word timings into 1-3 line balanced pages (max 3 lines, <= 800px per line)
        font = get_caption_font()
        pages = paginate_word_timings(
            normalized_words,
            font=font,
            min_words_per_page=4,
            max_words_per_page=9,
            max_lines=3,
            max_width=800.0
        )
        caption_cues: List[CaptionCue] = []

        for page_idx, page_lines in enumerate(pages):
            page_words = [wt for line in page_lines for wt in line]
            clause_lines = [" ".join([wt.word for wt in line]).upper() for line in page_lines]
            page_text = " ".join([wt.word for wt in page_words]).upper()

            for line_idx, line_words in enumerate(page_lines):
                for word_idx_on_line, wt in enumerate(line_words):
                    w_start = wt.start_seconds
                    w_end = wt.end_seconds

                    # Extend end_seconds to next word's start to ensure smooth non-flickering highlight
                    word_pos_in_page = sum(len(page_lines[l]) for l in range(line_idx)) + word_idx_on_line
                    if word_pos_in_page < len(page_words) - 1:
                        next_start = page_words[word_pos_in_page + 1].start_seconds
                        if next_start > w_start:
                            w_end = next_start
                    elif page_idx < len(pages) - 1 and len(pages[page_idx + 1]) > 0 and len(pages[page_idx + 1][0]) > 0:
                        next_page_first_start = pages[page_idx + 1][0][0].start_seconds
                        if next_page_first_start > w_start:
                            w_end = next_page_first_start
                    else:
                        w_end = min(total_duration, max(w_end + 0.2, w_start + 0.3))

                    caption_cues.append(CaptionCue(
                        text=wt.word.upper(),
                        start_seconds=w_start,
                        end_seconds=w_end,
                        segment_text=page_text,
                        lines=clause_lines,
                        active_line_index=line_idx,
                        active_word_index=word_idx_on_line,
                        active_word=wt.word.upper()
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
