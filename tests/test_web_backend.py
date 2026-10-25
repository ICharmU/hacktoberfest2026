"""
Tests for Web Backend API & Video Catalog using Python unittest
"""

import unittest
from fastapi.testclient import TestClient
from web.backend.app import app

class TestWebBackend(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_list_videos(self):
        response = self.client.get("/api/videos")
        self.assertEqual(response.status_code, 200)
        videos = response.json()
        self.assertIsInstance(videos, list)
        if len(videos) > 0:
            v = videos[0]
            self.assertIn("id", v)
            self.assertIn("title", v)
            self.assertIn("stream_url", v)
            self.assertIn("download_url", v)
            self.assertIn("created_at", v)

    def test_video_string_matching_filter(self):
        response = self.client.get("/api/videos")
        self.assertEqual(response.status_code, 200)
        videos = response.json()

        if videos:
            sample_title = videos[0]["title"]
            search_query = sample_title.split()[0].lower()
            matched = [
                v for v in videos
                if search_query in v["title"].lower()
                or search_query in v["topic"].lower()
                or search_query in v["id"].lower()
                or any(search_query in t.lower() for t in v.get("tags", []))
            ]
            self.assertGreaterEqual(len(matched), 1)
            self.assertEqual(matched[0]["id"], videos[0]["id"])

    def test_get_video_details(self):
        response = self.client.get("/api/videos")
        videos = response.json()
        if videos:
            test_id = videos[0]["id"]
            detail_res = self.client.get(f"/api/videos/{test_id}")
            self.assertEqual(detail_res.status_code, 200)
            data = detail_res.json()
            self.assertEqual(data["id"], test_id)
            self.assertIn("stream_url", data)
            self.assertIn("metadata", data)

    def test_get_settings(self):
        response = self.client.get("/api/settings")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("langfuse_host", data)
        self.assertIn("is_langfuse_enabled", data)
        self.assertIn("default_model", data)

    def test_update_settings(self):
        response = self.client.post("/api/settings", json={
            "langfuse_host": "https://cloud.langfuse.com",
            "ollama_host": "http://localhost:11434"
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "updated")

    def test_serve_frontend_root(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("html", response.headers.get("content-type", ""))
        self.assertIn("root", response.text)

if __name__ == "__main__":
    unittest.main()
