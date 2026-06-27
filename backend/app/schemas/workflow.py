"""
Pydantic v2 schemas for Synapse workflow integration with n8n.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class WorkflowStatus(StrEnum):
    """Possible execution states for an n8n workflow run."""

    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"
    WAITING = "waiting"
    CANCELED = "canceled"
    UNKNOWN = "unknown"


class WorkflowInfo(BaseModel):
    """Metadata for a single n8n workflow."""

    id: str = Field(description="Unique workflow identifier.")
    name: str = Field(description="Human-readable workflow name.")
    active: bool = Field(description="Whether the workflow is enabled.")
    tags: list[str] = Field(default_factory=list)


class WorkflowExecution(BaseModel):
    """State of a specific workflow execution."""

    execution_id: str = Field(description="n8n execution identifier.")
    workflow_id: str = Field(description="Parent workflow identifier.")
    status: WorkflowStatus = Field(description="Current execution status.")
    data: dict[str, Any] = Field(
        default_factory=dict,
        description="Raw execution data returned by n8n.",
    )


class RunWorkflowRequest(BaseModel):
    """Request body for POST /workflow/run."""

    workflow_id: str = Field(description="ID of the workflow to execute.")
    input_data: dict[str, Any] = Field(
        default_factory=dict,
        description="Payload forwarded to the workflow trigger.",
    )