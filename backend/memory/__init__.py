"""Research memory system for persistent storage and retrieval.

This module provides SQLite-based storage for previous research queries,
enabling similar query detection and knowledge reuse.
"""

from .research_memory import ResearchMemory, get_research_memory

__all__ = ["ResearchMemory", "get_research_memory"]
