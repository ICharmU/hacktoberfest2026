"""
Central configuration for the Video Generation Pipeline.
"""

from pathlib import Path
import json

ROOT_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = ROOT_DIR / "assets"
GAMEPLAY_DIR = ASSETS_DIR / "gameplay"
FONTS_DIR = ASSETS_DIR / "fonts"
STYLES_DIR = ASSETS_DIR / "styles"
OUTPUTS_DIR = ROOT_DIR / "outputs"

# Default paths
DEFAULT_GAMEPLAY_VIDEO = GAMEPLAY_DIR / "subway_surfers.mp4"
DEFAULT_FONT_FILE = FONTS_DIR / "Anton.ttf"

# Video dimensions (Vertical 9:16)
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
VIDEO_FPS = 30

# Ollama model configuration
OLLAMA_HOST = "http://localhost:11434"
DEFAULT_MODEL = "gemma4:12b"

# Voice configuration (edge-tts)
DEFAULT_VOICE = "en-US-ChristopherNeural"
DEFAULT_RATE = "+18%"
DEFAULT_PITCH = "+0Hz"

# Arrow flash configuration (arrows flash off for 0.1s every 0.5s)
ARROW_CYCLE_SECONDS = 0.5
ARROW_OFF_DURATION = 0.1

def load_caption_style(preset_name: str = "brainrot_viral") -> dict:
    style_file = STYLES_DIR / "caption_styles.json"
    if style_file.exists():
        with open(style_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("presets", {}).get(preset_name, {})
    return {
        "font_size": 76,
        "text_color": "#FFFF00",
        "stroke_color": "#000000",
        "stroke_width": 8,
        "shadow_color": "#000000",
        "shadow_offset": [6, 6],
        "max_width_ratio": 0.85,
        "all_caps": True,
        "box_padding": 20
    }
