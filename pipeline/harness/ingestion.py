"""
Article Ingestion Engine.
Scrapes clean article body text from URLs, local files, or searches via DDGS + trafilatura.
"""

from pathlib import Path
from typing import Tuple, Optional
import requests
import trafilatura
from ddgs import DDGS
from pipeline.observability import observe

class ArticleIngestion:
    def __init__(self, max_chars: int = 12000):
        self.max_chars = max_chars
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

    @observe(name="article_ingestion")
    def ingest(self, query_or_url: str) -> Tuple[str, str, Optional[str]]:
        """
        Returns (article_title, clean_article_text, source_url)
        """
        # 1. Local file path check
        local_path = Path(query_or_url)
        if local_path.exists() and local_path.is_file():
            print(f"[ingestion] Reading from local file: {local_path}...", flush=True)
            text = local_path.read_text(encoding="utf-8", errors="replace")
            return local_path.stem, text[:self.max_chars], str(local_path)

        # 2. Direct HTTP/HTTPS URL check
        if query_or_url.startswith("http://") or query_or_url.startswith("https://"):
            print(f"[ingestion] Scraping direct URL: {query_or_url}...", flush=True)
            title, text = self._extract_url(query_or_url)
            if text and len(text) > 200:
                return title, text[:self.max_chars], query_or_url

        # 3. Topic query -> Search DDGS for top articles
        print(f"[ingestion] Searching DDGS articles for topic: '{query_or_url}'...", flush=True)
        ddgs = DDGS()
        search_queries = [
            f"{query_or_url} deep dive history full story",
            f"{query_or_url} article background facts"
        ]

        found_articles = []
        for q in search_queries:
            try:
                results = list(ddgs.text(q, max_results=4))
                for item in results:
                    url = item.get("href")
                    if url and not url.endswith((".pdf", ".doc")):
                        found_articles.append((item.get("title", query_or_url), url, item.get("body", "")))
                if found_articles:
                    break
            except Exception as e:
                print(f"[ingestion] DDGS search notice: {e}", flush=True)

        # Attempt to scrape top article candidates
        for title, url, snippet in found_articles:
            print(f"[ingestion] Attempting article extraction from: {url}...", flush=True)
            extracted_title, extracted_text = self._extract_url(url)
            if extracted_text and len(extracted_text) > 300:
                print(f"[ingestion] Successfully extracted article: '{extracted_title}' ({len(extracted_text)} chars).", flush=True)
                return extracted_title, extracted_text[:self.max_chars], url

        # Fallback: combine search snippets if full web extraction was blocked
        print("[ingestion] Web scraping fallback: synthesizing search intelligence...", flush=True)
        snippets = "\n\n".join([f"### {t}\n{b}" for t, u, b in found_articles if b])
        if not snippets:
            snippets = f"Topic Overview for {query_or_url}. Detailed historical and biographical accounts."
        return query_or_url, snippets[:self.max_chars], None

    def _extract_url(self, url: str) -> Tuple[str, str]:
        try:
            downloaded = trafilatura.fetch_url(url)
            if not downloaded:
                resp = requests.get(url, headers=self.headers, timeout=8)
                if resp.status_code == 200:
                    downloaded = resp.text

            if downloaded:
                text = trafilatura.extract(
                    downloaded,
                    include_comments=False,
                    include_tables=True,
                    no_fallback=False
                )
                metadata = trafilatura.extract_metadata(downloaded)
                title = metadata.title if (metadata and metadata.title) else url
                return title or "Article", text or ""
        except Exception as e:
            print(f"[ingestion] Warning scraping {url}: {e}", flush=True)
        return "Article", ""
