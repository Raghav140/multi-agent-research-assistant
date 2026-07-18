"""Pydantic schemas for request/response models."""

from pydantic import BaseModel, Field


class ResearchRequest(BaseModel):
    """Research request schema."""

    query: str = Field(..., description="Research query", min_length=1, max_length=1000)
    context: str | None = Field(None, description="Additional context for the research")
    max_results: int = Field(default=10, description="Maximum number of results", ge=1, le=100)


class ResearchResponse(BaseModel):
    """Research response schema."""

    query: str
    results: list[dict[str, str]]
    summary: str
    sources: list[str]
