"""Providers module for external service integrations."""

from .llm import OllamaProvider
from .search import DuckDuckGoProvider

__all__ = ["OllamaProvider", "DuckDuckGoProvider"]
