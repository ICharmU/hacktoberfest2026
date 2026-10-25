"""
Image fetcher utilizing DDGS to source high-impact foreground images.
Guarantees real visual images for every beat (no text cards).
"""

import time
import math
from pathlib import Path
from typing import List, Optional
import requests
from PIL import Image, ImageDraw
from ddgs import DDGS
from pipeline.observability import observe

class ImageFetcher:
    def __init__(self, target_size=(880, 640)):
        self.target_size = target_size

    @observe(name="image_fetcher")
    def fetch_image(self, query: str, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"[images] Searching DDGS image for: '{query}'...", flush=True)
        
        # Clean query for search
        clean_query = query.replace("'", "").replace('"', "").strip()
        queries_to_try = [clean_query]
        
        # Add simplified query fallback (first 2-3 words)
        words = clean_query.split()
        if len(words) > 2:
            queries_to_try.append(" ".join(words[:2]))
            
        downloaded = False
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        
        for q in queries_to_try:
            if downloaded:
                break
            try:
                ddgs = DDGS()
                results = list(ddgs.images(q, max_results=6))
                for item in results:
                    # Try primary image URL, then fallback to thumbnail URL from Bing CDN
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
                                # Validate it is a valid image and scale nicely
                                with Image.open(output_path) as img:
                                    img = img.convert("RGBA")
                                    img.thumbnail(self.target_size, Image.Resampling.LANCZOS)
                                    img.save(output_path, "PNG")
                                downloaded = True
                                print(f"[images] Successfully downloaded real image for '{q}'.", flush=True)
                                break
                        except Exception:
                            continue
                    if downloaded:
                        break
            except Exception as e:
                print(f"[images] Warning during image search for '{q}': {e}", flush=True)
                time.sleep(0.5)

        if not downloaded:
            print(f"[images] Generating procedural visual graphic for '{query}'...", flush=True)
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
