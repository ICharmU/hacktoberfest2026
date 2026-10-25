"""
Langfuse Observability & Telemetry Integration.
Tracks LLM generation calls, researcher queries, TTS synthesis, asset fetches, and video composition.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root if present
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
env_file = ROOT_DIR / ".env"
if env_file.exists():
    load_dotenv(dotenv_path=env_file)
else:
    load_dotenv()

from langfuse import observe, get_client

_has_keys = bool(os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"))

def is_tracking_enabled() -> bool:
    return _has_keys

def init_observability():
    if is_tracking_enabled():
        host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
        print(f"[langfuse] Telemetry active -> Tracking to Langfuse ({host})", flush=True)
    else:
        print("[langfuse] Telemetry inactive (Set LANGFUSE_PUBLIC_KEY & LANGFUSE_SECRET_KEY in .env to track calls)", flush=True)

def flush_telemetry():
    """
    Flushes all queued events to Langfuse.
    """
    if is_tracking_enabled():
        try:
            client = get_client()
            client.flush()
            print("[langfuse] Telemetry events successfully flushed to Langfuse.", flush=True)
        except Exception as e:
            print(f"[langfuse] Warning: Failed to flush telemetry: {e}", flush=True)
