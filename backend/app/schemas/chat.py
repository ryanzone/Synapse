"""
Pydantic v2 schemas for Synapse chat endpoints.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class MessageRole(StrEnum):
    """OpenAI-compatible message roles."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class ChatMessage(BaseModel):
    """A single chat turn."""

    role: MessageRole = Field(description="Message role.")
    content: str = Field(description="Message text content.")
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatRequest(BaseModel):
    """Request body for POST /chat."""

    messages: list[ChatMessage] = Field(
        min_length=1,
        description="Conversation history ending with the latest user message.",
    )
    model: str | None = Field(
        default=None,
        description="Optional model override. Defaults to DEFAULT_MODEL.",
    )
    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Sampling temperature.",
    )
    max_tokens: int = Field(
        default=2048,
        ge=1,
        le=32768,
        description="Maximum number of tokens to generate.",
    )
    use_memory: bool = Field(
        default=True,
        description="Retrieve relevant memories before generation.",
    )
    stream: bool = Field(
        default=False,
        description="Enable streaming responses.",
    )


class ChatResponse(BaseModel):
    """Response body for POST /chat."""

    reply: str = Field(description="The assistant's response.")
    model: str = Field(description="Model used to generate the response.")
    memory_ids: list[str] = Field(
        default_factory=list,
        description="IDs of retrieved memories.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional response metadata.",
    )