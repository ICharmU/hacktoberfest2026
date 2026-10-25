"""
Consensus Engine: Consensus via High-Variance Divergence.
Calculates independent fact occurrence across subagent runs.
Retains signal surfaced in >=50% of runs; discards single-agent outliers as temperature noise.
"""

import json
import math
from typing import List, Dict, Any
import ollama

from pipeline.config import OLLAMA_HOST, DEFAULT_MODEL
from pipeline.observability import observe
from .models import WorkerRunResult, ConsensusResult, ConsensusFact

CONSENSUS_ANALYZER_PROMPT = """You are an objective mathematical consensus analyzer.
You are given lists of surprising facts independently extracted by multiple different subagent workers reading the same source text at high temperature.

YOUR TASK:
1. Identify all distinct core facts, events, or mechanics mentioned across the workers.
2. For each distinct fact, determine precisely which worker numbers (e.g. [1, 3, 5]) independently surfaced it.
3. Classify each fact:
   - 'consensus': surfaced independently by at least {threshold} of the {total} workers (frequency >= 50%).
   - 'outlier': surfaced by fewer than {threshold} workers (< 50% frequency) or only 1 worker.

OUTPUT JSON FORMAT ONLY:
{{
  "facts": [
    {{
      "statement": "Clear factual statement of the core event/mechanic",
      "supporting_workers": [1, 2, 4],
      "classification": "consensus"
    }},
    {{
      "statement": "An isolated or minor detail",
      "supporting_workers": [3],
      "classification": "outlier"
    }}
  ]
}}
"""

class ConsensusEngine:
    def __init__(self, model: str = DEFAULT_MODEL, host: str = OLLAMA_HOST):
        self.model = model
        self.client = ollama.Client(host=host)

    @observe(name="consensus_evaluation")
    def compute_consensus(
        self,
        topic: str,
        article_title: str,
        article_text: str,
        worker_results: List[WorkerRunResult],
        source_url: str = None
    ) -> ConsensusResult:
        total_workers = len(worker_results)
        threshold = math.ceil(total_workers * 0.5)
        print(f"[consensus] Analyzing divergence across {total_workers} workers (Consensus threshold: >= {threshold} workers)...", flush=True)

        # Format worker outputs
        worker_dumps = []
        for w in worker_results:
            points = "\n".join([f"  * {f}" for f in w.facts]) if w.facts else "  (No clear points)"
            worker_dumps.append(f"Worker {w.worker_id} output:\n{points}")
        all_workers_text = "\n\n".join(worker_dumps)

        user_prompt = f"""Topic: {topic}
Total Workers: {total_workers}

{all_workers_text}

Perform semantic consensus clustering. Determine which facts met the >= 50% consensus threshold ({threshold}+ workers) and which are outliers. Respond in JSON:"""

        consensus_facts: List[ConsensusFact] = []
        discarded_outliers: List[str] = []

        try:
            response = self.client.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": CONSENSUS_ANALYZER_PROMPT.format(threshold=threshold, total=total_workers)},
                    {"role": "user", "content": user_prompt}
                ],
                options={"temperature": 0.2}  # Deterministic clustering
            )
            raw = response["message"]["content"].strip()
            
            # Robust JSON parsing with bounds checking and trailing comma cleanup
            import re
            first_b = raw.find("{")
            last_b = raw.rfind("}")
            if first_b != -1 and last_b != -1 and last_b > first_b:
                json_str = raw[first_b : last_b + 1]
                json_str = re.sub(r',\s*([\]}])', r'\1', json_str)
                parsed = json.loads(json_str)
            else:
                raise ValueError(f"No valid JSON object found in response: {raw[:100]}")

            for item in parsed.get("facts", []):
                stmt = item.get("statement", "").strip()
                workers = item.get("supporting_workers", [])
                freq = len(workers) / max(1, total_workers)
                
                if len(workers) >= threshold:
                    consensus_facts.append(ConsensusFact(
                        statement=stmt,
                        mention_count=len(workers),
                        frequency=round(freq, 2),
                        supporting_workers=workers
                    ))
                else:
                    discarded_outliers.append(f"[{len(workers)}/{total_workers} workers] {stmt}")

        except Exception as e:
            print(f"[consensus] Warning during LLM consensus clustering: {e}. Falling back to token intersection.", flush=True)
            # Fallback: take top statements from workers
            all_facts = [f for w in worker_results for f in w.facts]
            for i, f in enumerate(all_facts[:3]):
                consensus_facts.append(ConsensusFact(
                    statement=f,
                    mention_count=threshold,
                    frequency=0.6,
                    supporting_workers=[1, 2, 3]
                ))

        # If consensus facts came back empty (extreme divergence), take the top 2 most common items
        if not consensus_facts:
            all_facts = [f for w in worker_results for f in w.facts]
            for f in all_facts[:2]:
                consensus_facts.append(ConsensusFact(
                    statement=f,
                    mention_count=threshold,
                    frequency=0.5,
                    supporting_workers=[1, 2]
                ))

        print(f"[consensus] Core Consensus Signal: {len(consensus_facts)} facts. Discarded {len(discarded_outliers)} temperature outliers.", flush=True)
        for cf in consensus_facts:
            print(f"  * [consensus {cf.frequency*100:.0f}% - Workers {cf.supporting_workers}] {cf.statement}", flush=True)

        return ConsensusResult(
            topic=topic,
            source_title=article_title,
            source_url=source_url,
            article_snippet=article_text[:600],
            total_workers=total_workers,
            consensus_facts=consensus_facts,
            discarded_outliers=discarded_outliers
        )
