"""
Top-level Orchestrator for the Local Shorts Ideation Harness.
Connects Ingestion -> High-Variance Worker Pool -> Consensus Filter -> Lead Director Agent.
"""

from typing import Optional
from pipeline.observability import observe
from .models import HarnessOutput, ConsensusResult
from .ingestion import ArticleIngestion
from .workers import WorkerPool
from .consensus import ConsensusEngine
from .director import LeadDirectorAgent

class IdeationHarness:
    def __init__(
        self,
        worker_model: str = "gemma4:e2b",
        director_model: str = "gemma4:12b",
        num_workers: int = 5,
        concurrency_limit: int = 2
    ):
        self.ingestion = ArticleIngestion()
        self.workers = WorkerPool(model=worker_model, num_workers=num_workers, concurrency_limit=concurrency_limit)
        self.consensus = ConsensusEngine(model=director_model)
        self.director = LeadDirectorAgent(model=director_model)

    @observe(name="ideation_harness_run")
    def run(self, query_or_url: str) -> HarnessOutput:
        print("=" * 60, flush=True)
        print(f"[harness] Starting Local Shorts Ideation Harness for: '{query_or_url}'", flush=True)
        print("=" * 60, flush=True)

        # 1. Ingestion
        title, clean_text, source_url = self.ingestion.ingest(query_or_url)
        print(f"[harness] Ingested source '{title}' ({len(clean_text)} characters).", flush=True)

        # 2. Worker Subagent Pool (High-Variance Divergence tau=0.90)
        worker_results = self.workers.dispatch_workers(clean_text)

        # 3. Consensus Engine (Frequency >= 50% signal vs outlier noise)
        consensus_result = self.consensus.compute_consensus(
            topic=query_or_url,
            article_title=title,
            article_text=clean_text,
            worker_results=worker_results,
            source_url=source_url
        )

        # 4. Lead Director Agent (Archetype sampling, 3s hook, 30-179s elongated script, takeaway)
        harness_output = self.director.direct(consensus_result)

        print("\n" + "=" * 60, flush=True)
        print(f"[harness] IDEATION HARNESS COMPLETE!", flush=True)
        print(f"  * Selected Archetype: {harness_output.selected_archetype}", flush=True)
        print(f"  * 3-Second Hook: \"{harness_output.hook.verbal_hook}\"", flush=True)
        print(f"  * Consensus Facts: {len(harness_output.consensus_facts)} validated", flush=True)
        print(f"  * Script Word Count: {len(harness_output.full_script.split())} words", flush=True)
        print("=" * 60 + "\n", flush=True)

        return harness_output
