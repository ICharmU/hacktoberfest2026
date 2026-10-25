"""
Date and Topic researcher utilizing DuckDuckGo Search (DDGS).
"""

from typing import List
from ddgs import DDGS
from .base import BaseResearcher, ResearchResult, FactItem

class DateResearcher(BaseResearcher):
    """
    Finds historical events, weird facts, or news associated with a specified date or topic.
    """
    def __init__(self, max_results: int = 8):
        self.max_results = max_results

    def research(self, query: str) -> ResearchResult:
        print(f"[researcher] Searching DDGS for: {query}...")
        
        # Build search queries (both specific date queries and notable event queries)
        queries = [
            f"this day in history {query} weird crazy facts",
            f"what happened on {query} bizarre events",
            f"{query} historical trivia"
        ]
        
        collected_facts: List[FactItem] = []
        ddgs = DDGS()
        
        for q in queries:
            try:
                results = list(ddgs.text(q, max_results=self.max_results))
                for item in results:
                    title = item.get("title", "")
                    snippet = item.get("body", "")
                    href = item.get("href", "")
                    if snippet and len(snippet) > 20:
                        collected_facts.append(
                            FactItem(title=title, snippet=snippet, url=href, date=query)
                        )
                if len(collected_facts) >= self.max_results:
                    break
            except Exception as e:
                print(f"[researcher] Warning during DDGS search for '{q}': {e}")
                continue
                
        # Fallback if no results returned from specific queries
        if not collected_facts:
            try:
                results = list(ddgs.text(query, max_results=self.max_results))
                for item in results:
                    collected_facts.append(
                        FactItem(
                            title=item.get("title", "Topic Fact"),
                            snippet=item.get("body", ""),
                            url=item.get("href", "")
                        )
                    )
            except Exception as e:
                print(f"[researcher] Fallback search error: {e}")

        # Compile a raw summary text block from snippets
        raw_summary = "\n".join([f"- {f.title}: {f.snippet}" for f in collected_facts[:8]])

        return ResearchResult(
            topic=query,
            target_date=query,
            facts=collected_facts[:10],
            raw_summary=raw_summary,
            metadata={"source": "duckduckgo_search", "query_count": len(queries)}
        )
