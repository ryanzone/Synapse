"""
Pydantic v2 schemas for Synapse memory records.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field, field_validator


class MemoryRecord(BaseModel):
    """A single stored memory with full metadata."""

    id: str = Field(description="UUID of the memory record.")
    text: str = Field(description="Memory content text.")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary key-value metadata.",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc),
        description="UTC timestamp when the memory was created.",
    )
    importance: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Importance score in [0.0, 1.0].",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Categorical tags for filtering.",
    )

    @field_validator("tags")
    @classmethod
    def strip_tags(cls, tags: list[str]) -> list[str]:
        """Normalise tags to lowercase stripped strings."""
        return [t.strip().lower() for t in tags if t.strip()]


class MemorySearchResult(BaseModel):
    """A memory record paired with its similarity score."""

    record: MemoryRecord
    score: float = Field(
        ge=0.0,
        le=1.0,
        description="Cosine similarity score.",
    )


class StoreMemoryRequest(BaseModel):
    """Request body for POST /memory/store."""

    text: str = Field(min_length=1, description="Memory content.")
    metadata: dict[str, Any] = Field(default_factory=dict)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    tags: list[str] = Field(default_factory=list)


class SearchMemoryRequest(BaseModel):
    """Request body for POST /memory/search."""

    query: str = Field(min_length=1, description="Semantic search query.")
    limit: int = Field(default=10, ge=1, le=100)
    score_threshold: float = Field(default=0.0, ge=0.0, le=1.0)
    tag_filter: list[str] | None = Field(default=None)