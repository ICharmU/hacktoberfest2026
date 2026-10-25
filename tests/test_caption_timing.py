"""
Unit tests for speech-synchronized karaoke captions, line balancing, and width constraints.
Validates width calculations, 3-lines maximum constraint, page advance, and PIL frame generation.
"""

import unittest
from pathlib import Path
from PIL import Image

from pipeline.tts.voice_actor import (
    balance_words_into_lines,
    paginate_word_timings,
    measure_line_width,
    get_caption_font,
    wrap_clause_lines,
    segment_text_into_clauses,
    CaptionCue,
    WordTiming
)
from pipeline.compositor.renderer import VideoCompositor
from pipeline.config import DEFAULT_FONT_FILE

class TestCaptionTiming(unittest.TestCase):
    def setUp(self):
        self.font = get_caption_font()

    def test_balance_words_into_lines_within_max_width(self):
        # Long words that previously overflowed to 1228px on a single 4-word line
        words = ["AN", "OVERWATCH", "LEAGUE", "CHAMPIONSHIP"]
        lines = balance_words_into_lines(words, font=self.font, max_lines=3, max_width=800.0)
        
        # Must be split into at least 2 lines to stay under 800px
        self.assertLessEqual(len(lines), 3)
        self.assertGreater(len(lines), 1)
        for l in lines:
            w = measure_line_width(l, self.font)
            self.assertLessEqual(w, 800.0, f"Line '{' '.join(l)}' width {w} exceeded 800px!")

    def test_balance_lines_equalizes_widths(self):
        # 6 words that should be split into 3 + 3 rather than 5 + 1
        words = ["HERE", "IS", "THE", "INSANE", "PART:", "DELISI"]
        lines = balance_words_into_lines(words, font=self.font, max_lines=3, max_width=800.0)
        self.assertEqual(len(lines), 2)
        # Verify no 1-word orphan
        self.assertGreater(len(lines[0]), 1)
        self.assertGreater(len(lines[1]), 1)
        w1 = measure_line_width(lines[0], self.font)
        w2 = measure_line_width(lines[1], self.font)
        self.assertLess(abs(w1 - w2), 300.0)

    def test_paginate_word_timings_respects_max_3_lines(self):
        # 30 words across sentences
        sample_text = (
            "Stop scrolling right now because what you think you know about "
            "cashew delisi supertf is literally backwards. Here is the insane part: "
            "DeLisi won both an Overwatch League championship."
        )
        words = sample_text.split()
        word_timings = [
            WordTiming(word=w, start_seconds=i * 0.3, end_seconds=(i + 1) * 0.3)
            for i, w in enumerate(words)
        ]
        pages = paginate_word_timings(
            word_timings,
            font=self.font,
            min_words_per_page=4,
            max_words_per_page=9,
            max_lines=3,
            max_width=800.0
        )
        self.assertGreater(len(pages), 1)
        for page_idx, page_lines in enumerate(pages):
            # 3 lines maximum
            self.assertLessEqual(len(page_lines), 3, f"Page {page_idx} exceeded 3 lines!")
            self.assertGreater(len(page_lines), 0)
            
            # Count total words on page
            page_words = [wt for l in page_lines for wt in l]
            # Must have at least 4 words per page (unless last page remnant)
            if page_idx < len(pages) - 1:
                self.assertGreaterEqual(len(page_words), 4, f"Page {page_idx} had fewer than 4 words!")
                
            # Every line must calculate and stay under 800px
            for l in page_lines:
                lw = measure_line_width([wt.word for wt in l], self.font)
                self.assertLessEqual(lw, 800.0, f"Line in page {page_idx} width {lw} exceeded 800px!")

    def test_caption_cue_timing_monotonicity(self):
        cues = [
            CaptionCue(
                text="HELLO",
                start_seconds=0.1,
                end_seconds=0.5,
                segment_text="HELLO WORLD",
                lines=["HELLO WORLD"],
                active_line_index=0,
                active_word_index=0,
                active_word="HELLO"
            ),
            CaptionCue(
                text="WORLD",
                start_seconds=0.5,
                end_seconds=1.1,
                segment_text="HELLO WORLD",
                lines=["HELLO WORLD"],
                active_line_index=0,
                active_word_index=1,
                active_word="WORLD"
            )
        ]
        for c in cues:
            self.assertGreater(c.end_seconds, c.start_seconds)
        self.assertAlmostEqual(cues[0].end_seconds, cues[1].start_seconds)

    def test_render_karaoke_caption_image(self):
        compositor = VideoCompositor(font_path=DEFAULT_FONT_FILE)
        lines = ["DID YOU KNOW THAT", "IN 2026 CRAZY THINGS", "HAPPENED EVERYWHERE"]
        
        # Render with word 1 on line 0 active ("YOU")
        img = compositor._render_karaoke_caption_image(
            lines=lines,
            active_line_idx=0,
            active_word_idx=1
        )
        self.assertIsInstance(img, Image.Image)
        self.assertEqual(img.size, (1080, 360))
        self.assertEqual(img.mode, "RGBA")
        
        bbox = img.getbbox()
        self.assertIsNotNone(bbox)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        self.assertGreater(w, 200)
        self.assertGreater(h, 50)
        # Must fit within safe width 820px
        self.assertLessEqual(w, 820)

if __name__ == "__main__":
    unittest.main()
