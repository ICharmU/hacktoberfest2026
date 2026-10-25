"""
Asset download helper for the video generation pipeline.
Downloads default caption fonts and provides voice preview generation.
"""

import sys
from pathlib import Path
import urllib.request

ASSETS_DIR = Path(__file__).resolve().parent
FONTS_DIR = ASSETS_DIR / "fonts"

# High-visibility open-source font URL (Montserrat-Black / Anton)
FONT_URLS = {
    "Anton.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/anton/Anton-Regular.ttf"
}

def ensure_fonts():
    FONTS_DIR.mkdir(parents=True, exist_ok=True)
    for font_name, url in FONT_URLS.items():
        dest = FONTS_DIR / font_name
        if not dest.exists():
            print(f"[assets] Downloading font: {font_name}...")
            try:
                urllib.request.urlretrieve(url, dest)
                print(f"[assets] Saved font to {dest}")
            except Exception as e:
                print(f"[assets] Warning: Could not download {font_name} from {url}: {e}")

if __name__ == "__main__":
    ensure_fonts()
