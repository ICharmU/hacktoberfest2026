"""
Data models for the Local Shorts Ideation Harness.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from pipeline.writer.script_writer import ScriptBeat

class Archetype(BaseModel):
    id: str
    name: str
    description: str
    hook_formula: str
    exemplar: str

class WorkerFact(BaseModel):
    fact: str = Field(description="Surprising mechanic, event, entity, or statistic")

class WorkerRunResult(BaseModel):
    worker_id: int
    raw_response: str
    facts: List[str] = Field(default_factory=list)

class ConsensusFact(BaseModel):
    statement: str
    mention_count: int
    frequency: float
    supporting_workers: List[int] = Field(default_factory=list)

class ConsensusResult(BaseModel):
    topic: str
    source_title: str
    source_url: Optional[str] = None
    article_snippet: str = ""
    total_workers: int
    consensus_facts: List[ConsensusFact] = Field(default_factory=list)
    discarded_outliers: List[str] = Field(default_factory=list)

class IdeaHook(BaseModel):
    verbal_hook: str = Field(description="High-energy 3-second opening hook line")
    visual_anchor_query: str = Field(description="2-4 word concrete image query for the visual anchor")

class ThreeBeatOutline(BaseModel):
    beat_1_hook: str = Field(description="Hook & initial context")
    beat_2_tension: str = Field(description="Escalating tension & comparative transition")
    beat_3_resolution: str = Field(description="Climax, resolution, and definitive takeaway")

class HarnessOutput(BaseModel):
    topic: str
    selected_archetype: str
    archetype_justification: str
    hook: IdeaHook
    outline: ThreeBeatOutline
    consensus_facts: List[str] = Field(default_factory=list)
    beats: List[ScriptBeat] = Field(default_factory=list)
    full_script: str
    title: str
    description: str
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
