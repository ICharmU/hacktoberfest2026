"""
Langfuse Observability & Telemetry Integration.
Tracks LLM generation calls, researcher queries, TTS synthesis, asset fetches, and video composition.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root or web/ directory if present
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
for env_candidate in [ROOT_DIR / ".env", ROOT_DIR / "web" / ".env", Path.cwd() / ".env"]:
    if env_candidate.exists():
        load_dotenv(dotenv_path=env_candidate, override=True)

# Sync LANGFUSE_HOST and LANGFUSE_BASE_URL
if not os.getenv("LANGFUSE_HOST") and os.getenv("LANGFUSE_BASE_URL"):
    os.environ["LANGFUSE_HOST"] = os.getenv("LANGFUSE_BASE_URL")
if not os.getenv("LANGFUSE_BASE_URL") and os.getenv("LANGFUSE_HOST"):
    os.environ["LANGFUSE_BASE_URL"] = os.getenv("LANGFUSE_HOST")

from langfuse import observe, get_client

def is_tracking_enabled() -> bool:
    return bool(os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"))

def init_observability():
    # Reload env files in case they were updated
    for env_candidate in [ROOT_DIR / ".env", ROOT_DIR / "web" / ".env", Path.cwd() / ".env"]:
        if env_candidate.exists():
            load_dotenv(dotenv_path=env_candidate, override=True)

    if not os.getenv("LANGFUSE_HOST") and os.getenv("LANGFUSE_BASE_URL"):
        os.environ["LANGFUSE_HOST"] = os.getenv("LANGFUSE_BASE_URL")
    if not os.getenv("LANGFUSE_BASE_URL") and os.getenv("LANGFUSE_HOST"):
        os.environ["LANGFUSE_BASE_URL"] = os.getenv("LANGFUSE_HOST")

    if is_tracking_enabled():
        host = os.getenv("LANGFUSE_HOST") or os.getenv("LANGFUSE_BASE_URL") or "https://cloud.langfuse.com"
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
