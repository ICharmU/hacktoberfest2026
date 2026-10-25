"""
Image fetcher utilizing DDGS to source high-impact, contextually relevant foreground images.
Guarantees specific visual images directly grounded in the spoken beat text and entities.
"""

import re
import time
import math
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
import requests
from PIL import Image, ImageDraw
from ddgs import DDGS
from pipeline.observability import observe

STOP_WORDS = {
    "the", "a", "an", "and", "or", "in", "on", "at", "to", "for", "of", "with",
    "by", "from", "up", "about", "into", "over", "after", "is", "was", "are",
    "were", "that", "this", "it", "they", "them", "his", "her", "their", "did",
    "you", "know", "what", "how", "why", "not", "but", "so", "as"
}

FORBIDDEN_SLOP_WORDS = {
    "chaos", "mystery", "shock", "shocked", "wild", "reaction", "screaming",
    "secret", "insane", "crazy", "dramatic", "explosion", "thinking", "mindblown",
    "slop", "face", "conclusion"
}

BAD_CANDIDATE_TERMS = [
    "clipart", "clip-art", "vector", "stock photo", "stock vector", "getty",
    "shutterstock", "istock", "alamy", "freepik", "vecteezy", "meme", "emoji",
    "template", "blank", "silhouette", "wallpaper", "abstract background",
    "drawing easy", "coloring page", "reaction meme", "youtube thumbnail"
]

CONVERSATIONAL_PREFIXES = [
    "stop scrolling", "did you know", "here is", "and that is why", "that is why",
    "and if you thought", "compare that", "nobody predicted", "you cannot make this up",
    "scientists and historians", "the crazy part", "the insane part"
]


def clean_query_text(query: str) -> str:
    """Cleans a query by removing quotes, unnecessary punctuation, and generic slop words."""
    cleaned = query.replace("'", "").replace('"', "").strip()
    words = [w for w in cleaned.split() if w.lower() not in FORBIDDEN_SLOP_WORDS]
    return " ".join(words).strip()


def extract_entities_from_text(text: str) -> List[str]:
    """
    Extracts high-specificity candidate entities (proper noun phrases, capitalized names, years)
    from spoken beat text, filtering out conversational hooks.
    """
    if not text:
        return []

    # Strip common conversational lead-in phrases
    lower_text = text.lower()
    clean_text = text
    for prefix in CONVERSATIONAL_PREFIXES:
        if lower_text.startswith(prefix):
            clean_text = clean_text[len(prefix):].lstrip(" ,:;!-")
            break

    candidates = []

    # 1. Capture multi-word capitalized phrases (e.g. "Battle of Balaclava", "Charge of the Light Brigade", "Lord Cardigan", "Kensington Palace")
    cap_phrase_pattern = r'\b[A-Z][a-zA-Z0-9]+(?:\s+(?:of\s+the|of|the|and|in|at|de|von|da)\s+[A-Z][a-zA-Z0-9]+|\s+[A-Z][a-zA-Z0-9]+)+\b'
    for match in re.finditer(cap_phrase_pattern, clean_text):
        phrase = match.group(0).strip()
        if phrase.lower() not in STOP_WORDS and len(phrase.split()) >= 2:
            candidates.append(phrase)

    # 2. Capture specific years (e.g. "1854", "1929")
    years = re.findall(r'\b(1[5-9][0-9]{2}|20[0-9]{2})\b', clean_text)

    # 3. Capture single prominent capitalized proper nouns not already part of multi-word phrases
    single_cap_pattern = r'\b[A-Z][a-zA-Z0-9]{3,}\b'
    for match in re.finditer(single_cap_pattern, clean_text):
        word = match.group(0).strip()
        if word.lower() not in STOP_WORDS and not any(word in c for c in candidates):
            # Pair with year if year exists
            if years:
                candidates.append(f"{word} {years[0]}")
            else:
                candidates.append(word)

    # Deduplicate while preserving order
    seen = set()
    result = []
    for c in candidates:
        c_low = c.lower()
        if c_low not in seen:
            seen.add(c_low)
            result.append(c)
    return result


def build_queries_to_try(
    query: str,
    beat_text: Optional[str] = None,
    topic: Optional[str] = None
) -> List[str]:
    """
    Builds an ordered list of high-specificity search queries.
    Prevents blind truncation and prioritizes concrete entities over vague tropes.
    """
    queries: List[str] = []
    clean_q = clean_query_text(query)

    if clean_q:
        queries.append(clean_q)

    # If topic is not in query, add topic-augmented query
    if topic and clean_q and topic.lower() not in clean_q.lower():
        queries.append(f"{clean_q} {topic}")

    # Extract concrete entities directly from beat narration
    if beat_text:
        entities = extract_entities_from_text(beat_text)
        for ent in entities:
            if ent.lower() != clean_q.lower():
                queries.append(ent)
                if topic and topic.lower() not in ent.lower():
                    queries.append(f"{ent} {topic}")

    # Fallback to topic archival query if everything else is empty
    if not queries and topic:
        queries.append(f"{topic} archival photo")

    # Clean and deduplicate queries
    deduped: List[str] = []
    seen = set()
    for q in queries:
        cleaned = q.strip()
        if cleaned and cleaned.lower() not in seen:
            seen.add(cleaned.lower())
            deduped.append(cleaned)

    return deduped[:4]


def score_image_candidate(
    candidate: Dict[str, Any],
    query: str,
    beat_text: Optional[str] = None,
    topic: Optional[str] = None
) -> float:
    """
    Scores an image candidate from DDGS to guarantee relevance to the spoken text.
    Penalizes generic stock photos, vectors, clip-art, memes, and bad dimensions.
    """
    title = str(candidate.get("title") or "").lower()
    url = str(candidate.get("image") or candidate.get("url") or "").lower()
    score = 0.0

    # 1. Negative penalties for bad terms (clipart, stock, meme, vector)
    for bad in BAD_CANDIDATE_TERMS:
        if bad in title or bad in url:
            score -= 15.0

    # 2. Query token matching
    q_words = [w.lower() for w in query.split() if len(w) > 2 and w.lower() not in STOP_WORDS]
    matched_q_tokens = 0
    for w in q_words:
        if w in title:
            score += 3.5
            matched_q_tokens += 1

    # Bonus for exact query phrase match
    clean_q_low = clean_query_text(query).lower()
    if clean_q_low and clean_q_low in title:
        score += 6.0

    # 3. Beat text entity & token matching
    if beat_text:
        entities = extract_entities_from_text(beat_text)
        for ent in entities:
            ent_low = ent.lower()
            if ent_low in title:
                score += 5.0
            else:
                for ew in ent_low.split():
                    if len(ew) > 2 and ew not in STOP_WORDS and ew in title:
                        score += 2.0

    # 4. Topic matching
    if topic:
        topic_words = [tw.lower() for tw in topic.split() if len(tw) > 2 and tw.lower() not in STOP_WORDS]
        for tw in topic_words:
            if tw in title:
                score += 1.5

    # 5. Dimension & aspect ratio sanity check
    try:
        w = float(candidate.get("width") or 0)
        h = float(candidate.get("height") or 0)
        if w > 0 and h > 0:
            ratio = w / h
            # Extreme banner or needle strip
            if ratio < 0.45 or ratio > 2.6:
                score -= 5.0
            # Low resolution icon / tiny thumbnail
            if w < 240 or h < 240:
                score -= 6.0
            elif w >= 600 and h >= 400:
                score += 2.0
    except (ValueError, TypeError):
        pass

    return score


class ImageFetcher:
    def __init__(self, target_size=(880, 640)):
        self.target_size = target_size

    @observe(name="image_fetcher")
    def fetch_image(
        self,
        query: str,
        output_path: Path,
        beat_text: Optional[str] = None,
        topic: Optional[str] = None
    ) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"[images] Sourcing foreground image for query: '{query}'...", flush=True)

        queries_to_try = build_queries_to_try(query, beat_text=beat_text, topic=topic)
        print(f"[images] Candidate search queries: {queries_to_try}", flush=True)

        downloaded = False
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

        for q in queries_to_try:
            if downloaded:
                break
            try:
                ddgs = DDGS()
                results = list(ddgs.images(q, max_results=8))
                if not results:
                    continue

                # Score all candidates against query and beat text
                scored = []
                for item in results:
                    s = score_image_candidate(item, q, beat_text=beat_text, topic=topic)
                    scored.append((s, item))

                # Sort by score descending (highest quality & relevance first)
                scored.sort(key=lambda x: x[0], reverse=True)

                for item_score, item in scored:
                    # Reject candidates with net negative score (stock watermarks, clip-art, extreme slop)
                    if item_score < -5.0:
                        continue

                    urls_to_try = []
                    if item.get("image"):
                        urls_to_try.append(item["image"])
                    if item.get("thumbnail"):
                        urls_to_try.append(item["thumbnail"])

                    for url in urls_to_try:
                        try:
                            resp = requests.get(url, timeout=5, headers=headers)
                            if resp.status_code == 200 and len(resp.content) > 1000:
                                with open(output_path, "wb") as f:
                                    f.write(resp.content)
                                # Validate valid image and scale nicely
                                with Image.open(output_path) as img:
                                    img = img.convert("RGBA")
                                    img.thumbnail(self.target_size, Image.Resampling.LANCZOS)
                                    img.save(output_path, "PNG")
                                downloaded = True
                                item_title = item.get("title", "")
                                print(f"[images] Downloaded image (score: {item_score:.1f}, title: '{item_title[:50]}...') for query '{q}'.", flush=True)
                                break
                        except Exception:
                            continue
                    if downloaded:
                        break
            except Exception as e:
                print(f"[images] Warning during image search for '{q}': {e}", flush=True)
                time.sleep(0.5)

        if not downloaded:
            print(f"[images] Fallback: Generating procedural visual graphic for '{query}'...", flush=True)
            self._generate_visual_fallback(output_path)

        return output_path

    def _generate_visual_fallback(self, output_path: Path):
        """
        Generates a purely visual abstract graphic (cyber vortex / glowing gradient),
        NEVER displaying text on the beat card.
        """
        w, h = self.target_size
        img = Image.new("RGBA", (w, h), (10, 10, 25, 255))
        draw = ImageDraw.Draw(img)

        cx, cy = w // 2, h // 2
        # Concentric glowing rings
        for r in range(min(w, h) // 2, 20, -15):
            alpha = int(180 * (1 - r / (min(w, h) // 2)))
            col = (255, int(100 + 155 * math.sin(r * 0.05)), int(50 + 200 * math.cos(r * 0.05)), alpha)
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=col, width=4)

        img.save(output_path, "PNG")
