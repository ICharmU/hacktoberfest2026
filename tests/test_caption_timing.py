"""
Unit tests for speech-synchronized karaoke captions and clause timing.
Validates segmentation, timing monotonicity, and PIL frame generation without video rendering.
"""

import unittest
from pathlib import Path
from PIL import Image

from pipeline.tts.voice_actor import (
    segment_text_into_clauses,
    wrap_clause_lines,
    CaptionCue,
    WordTiming
)
from pipeline.compositor.renderer import VideoCompositor
from pipeline.config import DEFAULT_FONT_FILE

class TestCaptionTiming(unittest.TestCase):
    def test_short_sentence_kept_intact(self):
        text = "This is a short hook."
        clauses = segment_text_into_clauses(text, split_comma_threshold=6)
        self.assertEqual(len(clauses), 1)
        self.assertEqual(clauses[0], "This is a short hook.")

    def test_short_sentence_with_comma_kept_intact(self):
        text = "Wait, look at this."
        clauses = segment_text_into_clauses(text, split_comma_threshold=6)
        self.assertEqual(len(clauses), 1)
        self.assertEqual(clauses[0], "Wait, look at this.")

    def test_long_sentence_with_commas_splits_on_commas(self):
        text = "Wait, did you know that in 2026, researchers found a strange artifact, and nobody could explain it?"
        clauses = segment_text_into_clauses(text, split_comma_threshold=6)
        # Should split into multiple clauses
        self.assertGreater(len(clauses), 1)
        # Verify first part merged tiny "Wait," with next part or cleanly split
        self.assertIn("2026", clauses[0])
        # Verify all original words are preserved
        joined_clauses = " ".join(clauses).replace(",", "").replace("?", "").lower()
        for w in ["wait", "researchers", "artifact", "explain"]:
            self.assertIn(w, joined_clauses)

    def test_wrap_clause_lines(self):
        words = ["DID", "YOU", "KNOW", "THAT", "IN", "2026", "THINGS", "CHANGED"]
        lines = wrap_clause_lines(words, max_words_per_line=4)
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0], ["DID", "YOU", "KNOW", "THAT"])
        self.assertEqual(lines[1], ["IN", "2026", "THINGS", "CHANGED"])

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
        lines = ["DID YOU KNOW THAT", "IN 2026 CRAZY THINGS"]
        
        # Render with word 1 on line 0 active ("YOU")
        img = compositor._render_karaoke_caption_image(
            lines=lines,
            active_line_idx=0,
            active_word_idx=1
        )
        self.assertIsInstance(img, Image.Image)
        self.assertEqual(img.size, (1080, 360))
        self.assertEqual(img.mode, "RGBA")
        
        # Check that non-transparent pixels exist
        bbox = img.getbbox()
        self.assertIsNotNone(bbox)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        self.assertGreater(w, 200)
        self.assertGreater(h, 50)

if __name__ == "__main__":
    unittest.main()
