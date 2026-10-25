"""
Abstract base researcher definition.
Allows dropping in the future 4-agent consensus harness seamlessly.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class FactItem(BaseModel):
    title: str
    snippet: str
    url: Optional[str] = None
    date: Optional[str] = None

class ResearchResult(BaseModel):
    topic: str
    target_date: Optional[str] = None
    facts: List[FactItem] = Field(default_factory=list)
    raw_summary: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)

class BaseResearcher(ABC):
    """
    Abstract researcher interface for plugging in single-agent or multi-agent harnesses.
    """
    @abstractmethod
    def research(self, query: str) -> ResearchResult:
        """
        Execute research for a given topic or date query.
        """
        pass
