"""
YouTube OAuth & Upload Manager
Handles Google OAuth 2.0 flow, token persistence, channel information, and resumable video uploads to YouTube Shorts.
"""

import os
import json
from pathlib import Path
from typing import Optional, Dict, Any, Callable
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow
import googleapiclient.discovery
from googleapiclient.http import MediaFileUpload

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
for env_candidate in [ROOT_DIR / ".env", ROOT_DIR / "web" / ".env", Path.cwd() / ".env"]:
    if env_candidate.exists():
        load_dotenv(dotenv_path=env_candidate, override=True)

CREDENTIALS_FILE = ROOT_DIR / ".youtube_credentials.json"
CLIENT_SECRETS_FILE = ROOT_DIR / "client_secrets.json"

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly"
]

PKCE_CACHE_FILE = ROOT_DIR / ".oauth_pkce.json"

class YouTubeManager:
    _pending_redirect_uri: Optional[str] = None
    _pending_code_verifier: Optional[str] = None

    @classmethod
    def get_pending_redirect_uri(cls) -> Optional[str]:
        return cls._pending_redirect_uri

    @classmethod
    def get_pending_code_verifier(cls) -> Optional[str]:
        if cls._pending_code_verifier:
            return cls._pending_code_verifier
        if PKCE_CACHE_FILE.exists():
            try:
                with open(PKCE_CACHE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("code_verifier")
            except Exception:
                pass
        return None

    @staticmethod
    def get_client_config() -> Optional[Dict[str, Any]]:
        """
        Retrieves client configuration from environment variables or client_secrets.json.
        """
        # Ensure latest env vars
        for env_candidate in [ROOT_DIR / ".env", ROOT_DIR / "web" / ".env", Path.cwd() / ".env"]:
            if env_candidate.exists():
                load_dotenv(dotenv_path=env_candidate, override=True)

        client_id = os.getenv("YOUTUBE_CLIENT_ID")
        client_secret = os.getenv("YOUTUBE_CLIENT_SECRET")
        if client_id and client_secret:
            return {
                "web": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
            }

        # 2. client_secrets.json
        if CLIENT_SECRETS_FILE.exists():
            try:
                with open(CLIENT_SECRETS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass

        return None

    @classmethod
    def get_auth_url(cls, redirect_uri: str) -> Dict[str, str]:
        """
        Generates Google OAuth authorization URL.
        """
        config = cls.get_client_config()
        if not config:
            raise ValueError("YouTube OAuth not configured. Provide YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET in Settings or provide client_secrets.json.")

        cls._pending_redirect_uri = redirect_uri
        flow = Flow.from_client_config(
            config,
            scopes=SCOPES,
            redirect_uri=redirect_uri
        )
        auth_url, state = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
            state=redirect_uri
        )
        cls._pending_code_verifier = flow.code_verifier

        # Cache PKCE verifier to survive potential server reloads
        try:
            with open(PKCE_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump({
                    "redirect_uri": redirect_uri,
                    "code_verifier": flow.code_verifier
                }, f)
        except Exception:
            pass

        return {
            "auth_url": auth_url,
            "state": state
        }

    @classmethod
    def exchange_code(cls, code: str, redirect_uri: str) -> Dict[str, Any]:
        """
        Exchanges authorization code for credentials and persists to disk.
        """
        config = cls.get_client_config()
        if not config:
            raise ValueError("YouTube OAuth configuration missing.")

        code_verifier = cls.get_pending_code_verifier()

        flow = Flow.from_client_config(
            config,
            scopes=SCOPES,
            redirect_uri=redirect_uri
        )
        if code_verifier:
            flow.code_verifier = code_verifier

        fetch_kwargs = {"code": code}
        if code_verifier:
            fetch_kwargs["code_verifier"] = code_verifier

        flow.fetch_token(**fetch_kwargs)
        credentials = flow.credentials

        creds_data = {
            "token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_uri": credentials.token_uri,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "scopes": credentials.scopes
        }

        with open(CREDENTIALS_FILE, "w", encoding="utf-8") as f:
            json.dump(creds_data, f, indent=2)

        # Cleanup temporary PKCE file
        if PKCE_CACHE_FILE.exists():
            try:
                PKCE_CACHE_FILE.unlink()
            except Exception:
                pass

        return cls.get_channel_status()

    @classmethod
    def get_credentials(cls) -> Optional[Credentials]:
        """
        Loads credentials from disk, refreshing if expired.
        """
        if not CREDENTIALS_FILE.exists():
            return None

        try:
            with open(CREDENTIALS_FILE, "r", encoding="utf-8") as f:
                creds_data = json.load(f)

            credentials = Credentials(
                token=creds_data.get("token"),
                refresh_token=creds_data.get("refresh_token"),
                token_uri=creds_data.get("token_uri", "https://oauth2.googleapis.com/token"),
                client_id=creds_data.get("client_id") or os.getenv("YOUTUBE_CLIENT_ID"),
                client_secret=creds_data.get("client_secret") or os.getenv("YOUTUBE_CLIENT_SECRET"),
                scopes=creds_data.get("scopes", SCOPES)
            )

            if credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
                # Update saved token
                creds_data["token"] = credentials.token
                with open(CREDENTIALS_FILE, "w", encoding="utf-8") as f:
                    json.dump(creds_data, f, indent=2)

            return credentials
        except Exception as e:
            print(f"[youtube] Error loading/refreshing credentials: {e}")
            return None

    @classmethod
    def get_channel_status(cls) -> Dict[str, Any]:
        """
        Checks if connected and retrieves channel details (name, thumbnail).
        """
        credentials = cls.get_credentials()
        has_config = cls.get_client_config() is not None

        if not credentials:
            return {
                "connected": False,
                "configured": has_config,
                "channel": None
            }

        try:
            youtube = googleapiclient.discovery.build("youtube", "v3", credentials=credentials)
            res = youtube.channels().list(part="snippet,statistics", mine=True).execute()
            items = res.get("items", [])
            if items:
                snippet = items[0].get("snippet", {})
                return {
                    "connected": True,
                    "configured": True,
                    "channel": {
                        "id": items[0].get("id"),
                        "title": snippet.get("title"),
                        "custom_url": snippet.get("customUrl"),
                        "thumbnail": snippet.get("thumbnails", {}).get("default", {}).get("url")
                    }
                }
            return {
                "connected": True,
                "configured": True,
                "channel": {"title": "Connected Channel"}
            }
        except Exception as e:
            return {
                "connected": False,
                "configured": has_config,
                "error": str(e),
                "channel": None
            }

    @classmethod
    def disconnect(cls) -> bool:
        """
        Removes stored credentials.
        """
        if CREDENTIALS_FILE.exists():
            try:
                CREDENTIALS_FILE.unlink()
                return True
            except Exception:
                return False
        return True

    @classmethod
    def upload_video(
        cls,
        video_path: Path,
        title: str,
        description: str,
        tags: Optional[list] = None,
        privacy_status: str = "unlisted",
        made_for_kids: bool = False,
        progress_callback: Optional[Callable[[int, str], None]] = None
    ) -> Dict[str, Any]:
        """
        Uploads a video to YouTube with resumable chunks.
        """
        credentials = cls.get_credentials()
        if not credentials:
            raise ValueError("YouTube account is not connected. Authenticate via OAuth first.")

        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")

        youtube = googleapiclient.discovery.build("youtube", "v3", credentials=credentials)

        # Clean tags (strip '#' if present since YouTube tags are comma-separated words)
        cleaned_tags = []
        for t in (tags or []):
            clean_t = t.lstrip('#').strip()
            if clean_t and clean_t not in cleaned_tags:
                cleaned_tags.append(clean_t)

        # YouTube Shorts best practice: add #shorts to title/description if not present
        if "#shorts" not in title.lower() and "#shorts" not in description.lower():
            title = f"{title} #shorts"

        body = {
            "snippet": {
                "title": title[:100],  # YouTube title limit 100 chars
                "description": description[:5000],
                "tags": cleaned_tags[:50],
                "categoryId": "24"  # Entertainment
            },
            "status": {
                "privacyStatus": privacy_status,  # public, unlisted, private
                "selfDeclaredMadeForKids": made_for_kids
            }
        }

        # 5MB chunks for progress reporting
        media = MediaFileUpload(
            str(video_path),
            chunksize=5 * 1024 * 1024,
            resumable=True,
            mimetype="video/mp4"
        )

        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media
        )

        if progress_callback:
            progress_callback(5, "Initiating YouTube upload session...")

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                percent = int(status.progress() * 95)
                if progress_callback:
                    progress_callback(percent, f"Uploading to YouTube: {percent}%")

        video_id = response.get("id")
        shorts_url = f"https://www.youtube.com/shorts/{video_id}"
        watch_url = f"https://www.youtube.com/watch?v={video_id}"

        if progress_callback:
            progress_callback(100, "Upload completed successfully!")

        return {
            "video_id": video_id,
            "shorts_url": shorts_url,
            "watch_url": watch_url,
            "title": response.get("snippet", {}).get("title"),
            "status": response.get("status", {}).get("privacyStatus")
        }
