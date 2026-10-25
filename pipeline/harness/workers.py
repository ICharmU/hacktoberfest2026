"""
Subagent Worker Pool running gemma4:e2b Q4 at high temperature (tau=0.85-0.95).
Executes open comprehension read-outs across parallel workers to induce high-variance divergence.
"""

import asyncio
import re
from typing import List
import ollama

from pipeline.config import OLLAMA_HOST
from pipeline.observability import observe
from .models import WorkerRunResult

WORKER_MODEL = "gemma4:e2b"
DEFAULT_NUM_WORKERS = 5
DEFAULT_TEMPERATURE = 0.90
DEFAULT_TOP_P = 0.90

SYSTEM_PROMPT = """You are an analytical reading subagent.
Read the provided source text and output a loose list of the 3 to 5 most surprising, counter-intuitive, absurd, or high-stakes mechanics/events.

RULES:
- Zero introductory fluff (no 'Here are the facts', no 'In this text').
- No scriptwriting, no meta-commentary, no conclusions.
- Output each point as a clear, standalone statement on its own line starting with '- '.
"""

class WorkerPool:
    def __init__(
        self,
        model: str = WORKER_MODEL,
        host: str = OLLAMA_HOST,
        num_workers: int = DEFAULT_NUM_WORKERS,
        concurrency_limit: int = 2
    ):
        self.model = model
        self.host = host
        self.num_workers = num_workers
        self.semaphore = asyncio.Semaphore(concurrency_limit)
        self.client = ollama.AsyncClient(host=host)

    @observe(name="worker_pool_dispatch")
    def dispatch_workers(self, article_text: str) -> List[WorkerRunResult]:
        """
        Synchronously runs the async worker pool.
        """
        return asyncio.run(self._dispatch_async(article_text))

    async def _dispatch_async(self, article_text: str) -> List[WorkerRunResult]:
        print(f"[workers] Dispatching {self.num_workers} parallel workers on '{self.model}' (tau={DEFAULT_TEMPERATURE}, top_p={DEFAULT_TOP_P})...", flush=True)
        tasks = [self._run_single_worker(i + 1, article_text) for i in range(self.num_workers)]
        results = await asyncio.gather(*tasks)
        print(f"[workers] Completed {len(results)} worker read-outs.", flush=True)
        return results

    @observe(name="single_subagent_worker", as_type="generation")
    async def _run_single_worker(self, worker_id: int, article_text: str) -> WorkerRunResult:
        async with self.semaphore:
            # Truncate text slightly if enormous to fit small 2B context smoothly
            clean_text = article_text[:8000]
            user_message = f"SOURCE TEXT:\n{clean_text}\n\nList 3-5 most surprising, absurd, counter-intuitive, or high-stakes facts/mechanics from the text above:"
            
            try:
                response = await self.client.chat(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_message}
                    ],
                    options={
                        "temperature": DEFAULT_TEMPERATURE,
                        "top_p": DEFAULT_TOP_P
                    }
                )
                raw_content = response["message"]["content"].strip()
                facts = self._extract_facts(raw_content)
                print(f"  [worker-{worker_id}] Extracted {len(facts)} high-variance points.", flush=True)
                return WorkerRunResult(
                    worker_id=worker_id,
                    raw_response=raw_content,
                    facts=facts
                )
            except Exception as e:
                print(f"  [worker-{worker_id}] Execution error: {e}", flush=True)
                return WorkerRunResult(worker_id=worker_id, raw_response="", facts=[])

    def _extract_facts(self, text: str) -> List[str]:
        lines = []
        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue
            # Strip bullet markers, numbers, or dashes
            cleaned = re.sub(r"^[-*•\d+.\s]+", "", line).strip()
            if cleaned and len(cleaned) > 15:
                lines.append(cleaned)
        return lines[:5]
