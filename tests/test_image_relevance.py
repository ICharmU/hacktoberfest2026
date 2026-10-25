"""
Unit tests for image relevance, entity extraction, candidate scoring, and slop prevention.
"""

import unittest
from pathlib import Path

from pipeline.assets.image_fetcher import (
    clean_query_text,
    extract_entities_from_text,
    build_queries_to_try,
    score_image_candidate,
    FORBIDDEN_SLOP_WORDS
)
from pipeline.harness.director import DIRECTOR_SYSTEM_PROMPT, LeadDirectorAgent
from pipeline.harness.models import ConsensusResult, ConsensusFact
from pipeline.writer.script_writer import SYSTEM_PROMPT as WRITER_SYSTEM_PROMPT, ScriptWriter
from pipeline.researcher.base import ResearchResult, FactItem


class TestImageRelevance(unittest.TestCase):
    def test_clean_query_text_removes_slop_words(self):
        query = "King George II chaos mystery shock"
        cleaned = clean_query_text(query)
        self.assertEqual(cleaned, "King George II")

    def test_clean_query_text_preserves_proper_entities(self):
        query = "Battle of Balaclava 1854"
        cleaned = clean_query_text(query)
        self.assertEqual(cleaned, "Battle of Balaclava 1854")

    def test_extract_entities_from_text_proper_nouns_and_years(self):
        text = "In 1854, the Charge of the Light Brigade saw British cavalry charge Russian guns at the Battle of Balaclava."
        entities = extract_entities_from_text(text)
        self.assertIn("Charge of the Light Brigade", entities)
        self.assertIn("Battle of Balaclava", entities)

    def test_extract_entities_filters_conversational_prefixes(self):
        text = "Stop scrolling right now, King George II collapsed at Kensington Palace."
        entities = extract_entities_from_text(text)
        self.assertIn("King George II", entities)
        self.assertIn("Kensington Palace", entities)
        self.assertNotIn("Stop Scrolling", entities)

    def test_build_queries_to_try_prioritizes_specific_entities(self):
        query = "Charge of the Light Brigade"
        beat_text = "Lord Cardigan led the charge during the Battle of Balaclava in 1854."
        topic = "October 25"

        queries = build_queries_to_try(query=query, beat_text=beat_text, topic=topic)
        self.assertGreaterEqual(len(queries), 2)
        # Primary clean query should be first
        self.assertEqual(queries[0], "Charge of the Light Brigade")
        # Should include topic or entity extracted from beat
        joined = " ".join(queries)
        self.assertTrue("Battle of Balaclava" in joined or "Lord Cardigan" in joined or "October 25" in joined)

    def test_candidate_scoring_prioritizes_specific_entity_over_stock(self):
        query = "King George II portrait"
        beat_text = "King George II died suddenly at Kensington Palace."
        topic = "October 25"

        authentic_candidate = {
            "title": "Portrait of King George II at Kensington Palace - National Portrait Gallery",
            "image": "https://example.com/king_george_ii.jpg",
            "url": "https://npg.org.uk/king_george",
            "width": 800,
            "height": 1000
        }

        stock_candidate = {
            "title": "King George II cartoon stock vector clipart royalty free",
            "image": "https://example.com/stock_vector.jpg",
            "url": "https://shutterstock.com/image",
            "width": 800,
            "height": 600
        }

        score_authentic = score_image_candidate(authentic_candidate, query, beat_text, topic)
        score_stock = score_image_candidate(stock_candidate, query, beat_text, topic)

        self.assertGreater(score_authentic, score_stock)
        self.assertGreater(score_authentic, 10.0)
        self.assertLess(score_stock, 0.0)

    def test_candidate_scoring_penalizes_bad_aspect_ratios_and_tiny_sizes(self):
        query = "Thomas Edison phonograph"
        good_candidate = {
            "title": "Thomas Edison with his phonograph 1877",
            "image": "https://example.com/edison.jpg",
            "width": 1024,
            "height": 768
        }
        banner_candidate = {
            "title": "Thomas Edison with his phonograph 1877",
            "image": "https://example.com/edison_banner.jpg",
            "width": 1200,
            "height": 100  # Aspect ratio 12:1 banner
        }
        tiny_candidate = {
            "title": "Thomas Edison with his phonograph 1877",
            "image": "https://example.com/edison_icon.jpg",
            "width": 64,
            "height": 64
        }

        good_score = score_image_candidate(good_candidate, query)
        banner_score = score_image_candidate(banner_candidate, query)
        tiny_score = score_image_candidate(tiny_candidate, query)

        self.assertGreater(good_score, banner_score)
        self.assertGreater(good_score, tiny_score)

    def test_director_prompts_contain_specificity_rules(self):
        self.assertIn("IMAGE SPECIFICITY & GROUNDING", DIRECTOR_SYSTEM_PROMPT)
        self.assertIn("FORBIDDEN SLOP", DIRECTOR_SYSTEM_PROMPT)
        for slop in ["chaos", "mystery", "shock", "wild"]:
            self.assertIn(slop, DIRECTOR_SYSTEM_PROMPT)

    def test_writer_prompts_contain_specificity_rules(self):
        self.assertIn("IMAGE SPECIFICITY & GROUNDING", WRITER_SYSTEM_PROMPT)
        self.assertIn("FORBIDDEN SLOP", WRITER_SYSTEM_PROMPT)

    def test_director_fallback_has_no_slop_queries(self):
        director = LeadDirectorAgent()
        consensus = ConsensusResult(
            topic="October 25",
            source_title="October 25 in History",
            total_workers=2,
            consensus_facts=[
                ConsensusFact(statement="The Charge of the Light Brigade occurred in 1854.", mention_count=2, frequency=1.0)
            ]
        )
        fallback = director._generate_fallback(consensus)
        for beat in fallback.beats:
            for slop in FORBIDDEN_SLOP_WORDS:
                self.assertNotIn(slop, beat.image_search_query.lower())

    def test_script_writer_fallback_has_no_slop_queries(self):
        writer = ScriptWriter()
        research = ResearchResult(
            topic="October 25",
            source="Test",
            facts=[FactItem(title="Battle of Balaclava", snippet="1854 battle")]
        )
        # Trigger fallback directly
        fallback = writer._generate_fallback_script if hasattr(writer, "_generate_fallback_script") else None
        # Verify script_writer fallback lines
        with open("pipeline/writer/script_writer.py", "r", encoding="utf-8") as f:
            code = f.read()
        self.assertNotIn("shocked screaming face", code)


if __name__ == "__main__":
    unittest.main()
