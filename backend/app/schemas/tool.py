"""
Pydantic v2 schemas for Synapse agent tools.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ToolStatus(StrEnum):
    """Execution state of a tool call."""

    SUCCESS = "success"
    ERROR = "error"
    SKIPPED = "skipped"


class ToolDefinition(BaseModel):
    """Describes an available tool the agent may invoke."""

    name: str = Field(description="Unique tool identifier.")
    description: str = Field(description="Human-readable purpose of the tool.")
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="JSON Schema describing accepted parameters.",
    )


class ToolCall(BaseModel):
    """A single tool invocation request from the planner."""

    tool_name: str = Field(description="Name of the tool to invoke.")
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Validated parameters for the call.",
    )


class ToolResult(BaseModel):
    """The outcome of executing a tool call."""

    tool_name: str = Field(description="Name of the executed tool.")
    status: ToolStatus = Field(description="Execution status.")
    output: Any = Field(
        default=None,
        description="Return value produced by the tool.",
    )
    error: str | None = Field(
        default=None,
        description="Error message if execution failed.",
    )
    duration_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Execution time in milliseconds.",
    )