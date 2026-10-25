"""
FastAPI Backend Application for Brainrot Video Generator
Provides:
- Job orchestration with SSE streaming for live progress & logs
- Catalog of previously generated videos from /outputs with metadata
- Settings management persisting to root .env
- Direct video streaming with byte-range support
"""

import asyncio
import datetime
import io
import json
import os
from pathlib import Path
import sys
import threading
import uuid
from typing import Dict, Any, Optional, List

from dotenv import load_dotenv, set_key
from fastapi import FastAPI, BackgroundTasks, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from pipeline.config import (
    OUTPUTS_DIR,
    DEFAULT_MODEL,
    DEFAULT_VOICE,
    DEFAULT_RATE,
    DEFAULT_PITCH
)
from pipeline.main import run_pipeline
from pipeline.observability import is_tracking_enabled, init_observability

# Load all potential .env locations
ENV_FILES = [
    ROOT_DIR / ".env",
    ROOT_DIR / "web" / ".env",
    Path.cwd() / ".env"
]
for candidate in ENV_FILES:
    if candidate.exists():
        load_dotenv(dotenv_path=candidate, override=True)

# Sync LANGFUSE_HOST and LANGFUSE_BASE_URL
if not os.getenv("LANGFUSE_HOST") and os.getenv("LANGFUSE_BASE_URL"):
    os.environ["LANGFUSE_HOST"] = os.getenv("LANGFUSE_BASE_URL")
if not os.getenv("LANGFUSE_BASE_URL") and os.getenv("LANGFUSE_HOST"):
    os.environ["LANGFUSE_BASE_URL"] = os.getenv("LANGFUSE_HOST")

app = FastAPI(
    title="Brainrot Slop Pipeline API",
    description="Studio Backend for Video Generation, Catalog, and Observability",
    version="1.0.0"
)

# Enable CORS for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory jobs tracking
# job_id -> { "status": str, "events_queue": asyncio.Queue, "history": list, "loop": loop }
active_jobs: Dict[str, Dict[str, Any]] = {}
app_loop: Optional[asyncio.AbstractEventLoop] = None

@app.on_event("startup")
async def startup_event():
    global app_loop
    app_loop = asyncio.get_running_loop()


# ============================================================================
# Models
# ============================================================================

from web.backend.youtube_manager import YouTubeManager

class GenerateRequest(BaseModel):
    topic: str
    model: str = DEFAULT_MODEL
    worker_model: str = "gemma4:e2b"
    num_workers: int = 5
    voice: str = DEFAULT_VOICE
    rate: str = DEFAULT_RATE
    pitch: str = DEFAULT_PITCH
    legacy: bool = False

class SettingsUpdateRequest(BaseModel):
    langfuse_public_key: Optional[str] = None
    langfuse_secret_key: Optional[str] = None
    langfuse_host: Optional[str] = None
    ollama_host: Optional[str] = None
    default_model: Optional[str] = None
    youtube_client_id: Optional[str] = None
    youtube_client_secret: Optional[str] = None

class YouTubeUploadRequest(BaseModel):
    title: str
    description: str
    tags: Optional[List[str]] = None
    privacy_status: str = "unlisted"
    made_for_kids: bool = False


# ============================================================================
# Job Execution & Progress Broadcast
# ============================================================================

class StreamCapture(io.TextIOBase):
    """Captures print output and feeds it to job logs & event queue."""
    def __init__(self, original_stream, on_line_callback):
        self.original_stream = original_stream
        self.on_line_callback = on_line_callback
        self._buffer = ""

    def write(self, s: str) -> int:
        self.original_stream.write(s)
        self.original_stream.flush()
        self._buffer += s
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            line = line.strip()
            if line:
                self.on_line_callback(line)
        return len(s)

    def flush(self):
        self.original_stream.flush()


def run_pipeline_job(job_id: str, req: GenerateRequest, loop: asyncio.AbstractEventLoop):
    job = active_jobs.get(job_id)
    if not job:
        return

    q: asyncio.Queue = job["events_queue"]

    def post_event(event_type: str, payload: dict):
        event_data = {
            "type": event_type,
            "timestamp": datetime.datetime.now().isoformat(),
            **payload
        }
        job["history"].append(event_data)
        if loop and loop.is_running():
            asyncio.run_coroutine_threadsafe(q.put(event_data), loop)

    def on_log_line(line: str):
        post_event("log", {"message": line})

    def progress_callback(stage: str, percent: int, message: str, data: Optional[Dict[str, Any]] = None):
        post_event("progress", {
            "stage": stage,
            "percent": percent,
            "message": message,
            "data": data or {}
        })

    old_stdout = sys.stdout
    old_stderr = sys.stderr
    capture = StreamCapture(old_stdout, on_log_line)

    try:
        sys.stdout = capture
        sys.stderr = capture
        job["status"] = "running"
        post_event("status", {"status": "running", "message": f"Pipeline started for topic '{req.topic}'"})

        run_dir = run_pipeline(
            topic=req.topic,
            model=req.model,
            worker_model=req.worker_model,
            num_workers=req.num_workers,
            voice=req.voice,
            rate=req.rate,
            pitch=req.pitch,
            legacy=req.legacy,
            progress_callback=progress_callback
        )

        output_id = run_dir.name
        job["status"] = "completed"
        job["output_id"] = output_id
        post_event("complete", {
            "message": "Video generation finished!",
            "output_id": output_id,
            "run_dir": str(run_dir),
            "video_url": f"/api/videos/{output_id}/stream"
        })
    except Exception as exc:
        job["status"] = "failed"
        job["error"] = str(exc)
        post_event("error", {
            "message": f"Error running pipeline: {str(exc)}"
        })
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr
        # Push termination signal
        if loop and loop.is_running():
            asyncio.run_coroutine_threadsafe(q.put(None), loop)


# ============================================================================
# API Endpoints
# ============================================================================

@app.post("/api/generate")
async def start_generation(req: GenerateRequest):
    global app_loop
    if not app_loop:
        app_loop = asyncio.get_running_loop()

    job_id = str(uuid.uuid4())[:8]
    events_queue = asyncio.Queue()
    active_jobs[job_id] = {
        "id": job_id,
        "req": req.dict(),
        "status": "queued",
        "created_at": datetime.datetime.now().isoformat(),
        "events_queue": events_queue,
        "history": [],
        "output_id": None
    }

    t = threading.Thread(
        target=run_pipeline_job,
        args=(job_id, req, app_loop),
        daemon=True
    )
    t.start()

    return {
        "job_id": job_id,
        "status": "started",
        "stream_url": f"/api/stream/{job_id}"
    }


@app.get("/api/stream/{job_id}")
async def stream_progress(job_id: str, request: Request):
    job = active_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    events_queue: asyncio.Queue = job["events_queue"]

    async def event_generator():
        # First yield any historic events
        for evt in job["history"]:
            yield f"data: {json.dumps(evt)}\n\n"

        # If job already ended and queue is drained
        if job["status"] in ("completed", "failed") and events_queue.empty():
            return

        while True:
            if await request.is_disconnected():
                break
            try:
                event = await asyncio.wait_for(events_queue.get(), timeout=20.0)
                if event is None:
                    # Stream completed
                    break
                yield f"data: {json.dumps(event)}\n\n"
            except asyncio.TimeoutError:
                # Keep-alive heartbeat ping
                yield ": keepalive\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.get("/api/videos")
async def list_videos():
    """
    Scans /outputs folder and returns list of all generated videos with their metadata.
    Sorted descending by creation timestamp.
    """
    videos = []
    if not OUTPUTS_DIR.exists():
        return videos

    for entry in OUTPUTS_DIR.iterdir():
        if entry.is_dir():
            video_path = entry / "video.mp4"
            if not video_path.exists():
                continue

            metadata_path = entry / "metadata.json"
            meta = {}
            if metadata_path.exists():
                try:
                    with open(metadata_path, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                except Exception:
                    pass

            stat = video_path.stat()
            created_at = meta.get("created_at")
            if not created_at:
                created_at = datetime.datetime.fromtimestamp(stat.st_mtime).isoformat()

            videos.append({
                "id": entry.name,
                "title": meta.get("title") or entry.name.replace("_", " "),
                "topic": meta.get("topic") or "",
                "description": meta.get("description") or "",
                "tags": meta.get("tags") or [],
                "duration_seconds": meta.get("duration_seconds") or 0.0,
                "created_at": created_at,
                "size_bytes": stat.st_size,
                "stream_url": f"/api/videos/{entry.name}/stream",
                "download_url": f"/api/videos/{entry.name}/download",
                "has_metadata": metadata_path.exists()
            })

    # Sort newest first
    videos.sort(key=lambda x: x["created_at"], reverse=True)
    return videos


@app.get("/api/videos/{video_id}")
async def get_video_details(video_id: str):
    video_dir = OUTPUTS_DIR / video_id
    if not video_dir.exists() or not video_dir.is_dir():
        raise HTTPException(status_code=404, detail="Video directory not found")

    video_path = video_dir / "video.mp4"
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Video file not found")

    metadata_path = video_dir / "metadata.json"
    metadata = {}
    if metadata_path.exists():
        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)
        except Exception as e:
            metadata = {"error": f"Failed to parse metadata: {e}"}

    stat = video_path.stat()
    return {
        "id": video_id,
        "title": metadata.get("title", video_id),
        "topic": metadata.get("topic", ""),
        "description": metadata.get("description", ""),
        "tags": metadata.get("tags", []),
        "duration_seconds": metadata.get("duration_seconds", 0.0),
        "created_at": metadata.get("created_at", datetime.datetime.fromtimestamp(stat.st_mtime).isoformat()),
        "stream_url": f"/api/videos/{video_id}/stream",
        "download_url": f"/api/videos/{video_id}/download",
        "metadata": metadata
    }


@app.get("/api/videos/{video_id}/stream")
async def stream_video(video_id: str):
    video_path = OUTPUTS_DIR / video_id / "video.mp4"
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Video file not found")
    return FileResponse(
        path=str(video_path),
        media_type="video/mp4",
        filename="video.mp4"
    )


@app.get("/api/videos/{video_id}/download")
async def download_video(video_id: str):
    video_path = OUTPUTS_DIR / video_id / "video.mp4"
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Video file not found")
    return FileResponse(
        path=str(video_path),
        media_type="video/mp4",
        filename=f"brainrot_{video_id}.mp4"
    )


# ============================================================================
# Settings & Observability Management
# ============================================================================

def mask_key(k: Optional[str]) -> str:
    if not k:
        return ""
    if len(k) <= 8:
        return "********"
    return k[:6] + "..." + k[-4:]


@app.get("/api/settings")
async def get_settings():
    """
    Returns current active configurations and Langfuse connection status.
    """
    pub_key = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    sec_key = os.getenv("LANGFUSE_SECRET_KEY", "")
    host = os.getenv("LANGFUSE_HOST") or os.getenv("LANGFUSE_BASE_URL") or "https://cloud.langfuse.com"
    ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")

    tracking = is_tracking_enabled()

    yt_status = YouTubeManager.get_channel_status()

    return {
        "langfuse_public_key": pub_key,
        "langfuse_secret_key_masked": mask_key(sec_key),
        "has_langfuse_secret": bool(sec_key),
        "langfuse_host": host,
        "ollama_host": ollama_host,
        "is_langfuse_enabled": tracking,
        "default_model": DEFAULT_MODEL,
        "default_voice": DEFAULT_VOICE,
        "youtube_client_id": os.getenv("YOUTUBE_CLIENT_ID", ""),
        "youtube_client_secret_masked": mask_key(os.getenv("YOUTUBE_CLIENT_SECRET", "")),
        "has_youtube_secret": bool(os.getenv("YOUTUBE_CLIENT_SECRET")),
        "youtube_status": yt_status
    }


@app.post("/api/settings")
async def update_settings(req: SettingsUpdateRequest):
    """
    Persistently updates .env file with new credentials and refreshes in-memory environment.
    """
    primary_env = ROOT_DIR / ".env"
    if not primary_env.exists():
        primary_env.touch()

    target_envs = [primary_env]
    web_env = ROOT_DIR / "web" / ".env"
    if web_env.exists():
        target_envs.append(web_env)

    updates = {}
    if req.langfuse_public_key is not None:
        updates["LANGFUSE_PUBLIC_KEY"] = req.langfuse_public_key.strip()
    if req.langfuse_secret_key is not None and req.langfuse_secret_key.strip():
        updates["LANGFUSE_SECRET_KEY"] = req.langfuse_secret_key.strip()
    if req.langfuse_host is not None:
        host_val = req.langfuse_host.strip()
        updates["LANGFUSE_HOST"] = host_val
        updates["LANGFUSE_BASE_URL"] = host_val
    if req.ollama_host is not None:
        updates["OLLAMA_HOST"] = req.ollama_host.strip()
    if req.youtube_client_id is not None:
        updates["YOUTUBE_CLIENT_ID"] = req.youtube_client_id.strip()
    if req.youtube_client_secret is not None and req.youtube_client_secret.strip():
        updates["YOUTUBE_CLIENT_SECRET"] = req.youtube_client_secret.strip()

    for env_target in target_envs:
        for k, v in updates.items():
            try:
                set_key(str(env_target), k, v)
            except Exception:
                pass

    for k, v in updates.items():
        os.environ[k] = v

    # Reload observability
    init_observability()

    return {
        "status": "updated",
        "is_langfuse_enabled": is_tracking_enabled(),
        "langfuse_host": os.getenv("LANGFUSE_HOST") or os.getenv("LANGFUSE_BASE_URL") or "https://cloud.langfuse.com",
        "youtube_status": YouTubeManager.get_channel_status()
    }


# ============================================================================
# YouTube Integration & Direct Upload
# ============================================================================

@app.get("/api/youtube/status")
async def get_youtube_status():
    return YouTubeManager.get_channel_status()


@app.get("/api/youtube/auth/url")
async def get_youtube_auth_url(redirect_uri: Optional[str] = None):
    if not redirect_uri:
        redirect_uri = "http://localhost:8000/api/youtube/auth/callback"
    try:
        return YouTubeManager.get_auth_url(redirect_uri=redirect_uri)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/youtube/auth/callback")
async def youtube_auth_callback(code: str, state: Optional[str] = None, request: Request = None):
    host_header = request.headers.get("host", "localhost:8000") if request else "localhost:8000"
    redirect_uri = f"http://{host_header}/api/youtube/auth/callback"
    try:
        YouTubeManager.exchange_code(code=code, redirect_uri=redirect_uri)
        return RedirectResponse(url="/?youtube_connected=true")
    except Exception as e:
        try:
            YouTubeManager.exchange_code(code=code, redirect_uri="http://localhost:8000/api/youtube/auth/callback")
            return RedirectResponse(url="/?youtube_connected=true")
        except Exception as inner_e:
            return RedirectResponse(url=f"/?youtube_error={str(inner_e)}")


@app.post("/api/youtube/disconnect")
async def disconnect_youtube():
    success = YouTubeManager.disconnect()
    return {"status": "disconnected" if success else "failed"}


@app.post("/api/youtube/upload/{video_id}")
async def upload_to_youtube(video_id: str, req: YouTubeUploadRequest):
    video_dir = OUTPUTS_DIR / video_id
    if not video_dir.exists() or not video_dir.is_dir():
        raise HTTPException(status_code=404, detail="Video directory not found")

    video_path = video_dir / "video.mp4"
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Video file not found")

    try:
        result = YouTubeManager.upload_video(
            video_path=video_path,
            title=req.title,
            description=req.description,
            tags=req.tags or [],
            privacy_status=req.privacy_status,
            made_for_kids=req.made_for_kids
        )

        metadata_path = video_dir / "metadata.json"
        if metadata_path.exists():
            try:
                with open(metadata_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                meta["youtube_id"] = result["video_id"]
                meta["youtube_shorts_url"] = result["shorts_url"]
                meta["youtube_watch_url"] = result["watch_url"]
                meta["youtube_uploaded_at"] = datetime.datetime.now().isoformat()
                with open(metadata_path, "w", encoding="utf-8") as f:
                    json.dump(meta, f, indent=2)
            except Exception:
                pass

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"YouTube upload failed: {str(e)}")


# ============================================================================
# Static Files / Frontend Serving
# ============================================================================

# Mount outputs directory directly
if OUTPUTS_DIR.exists():
    app.mount("/outputs", StaticFiles(directory=str(OUTPUTS_DIR)), name="outputs")

# If frontend dist exists, mount it
FRONTEND_DIST = ROOT_DIR / "web" / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")


def main():
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    print(f"Starting Brainrot Web Studio on http://localhost:{port}")
    uvicorn.run("web.backend.app:app", host="0.0.0.0", port=port, reload=True)


if __name__ == "__main__":
    main()
