"""
Agent state container for a single reasoning cycle in Synapse.

The AgentState is created at the start of each cycle and mutated by
each pipeline stage (planner → memory → context → reasoning →
tool selection → execution → reflection → memory storage).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.schemas.chat import ChatMessage
from app.schemas.memory import MemorySearchResult
from app.schemas.tool import ToolCall, ToolResult


@dataclass
class AgentState:
    """
    Mutable state for a single agent reasoning cycle.

    Attributes:
        session_id:          Unique identifier for the current conversation session.
        user_input:          Raw user message text.
        conversation_history:Full message history including the current user turn.
        plan:                Structured plan produced by the Planner.
        retrieved_memories:  Memories fetched from Qdrant relevant to the input.
        context:             Assembled prompt context string sent to the LLM.
        reasoning_output:    Raw LLM output from the reasoning step.
        selected_tools:      Tool calls the LLM decided to invoke.
        tool_results:        Results from executing each tool call.
        reflection:          Self-critique / quality assessment from the reflector.
        final_response:      Polished response returned to the user.
        stored_memory_id:    ID of the memory record saved after this cycle.
        metadata:            Arbitrary key-value bag for cross-stage data.
        started_at:          UTC timestamp when the cycle began.
        completed_at:        UTC timestamp when the cycle finished (or None).
        error:               First error encountered, or None.
    """

    session_id: str
    user_input: str
    conversation_history: list[ChatMessage] = field(default_factory=list)

    # Pipeline outputs — populated progressively
    plan: dict[str, Any] = field(default_factory=dict)
    retrieved_memories: list[MemorySearchResult] = field(default_factory=list)
    context: str = ""
    reasoning_output: str = ""
    selected_tools: list[ToolCall] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)
    reflection: str = ""
    final_response: str = ""
    stored_memory_id: str | None = None

    # Housekeeping
    metadata: dict[str, Any] = field(default_factory=dict)
    started_at: datetime = field(
        default_factory=lambda: datetime.now(tz=timezone.utc)
    )
    completed_at: datetime | None = None
    error: str | None = None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def mark_complete(self) -> None:
        """Record the cycle completion timestamp."""
        self.completed_at = datetime.now(tz=timezone.utc)

    def mark_error(self, message: str) -> None:
        """Record an error and mark the cycle as finished."""
        self.error = message
        self.mark_complete()

    @property
    def elapsed_ms(self) -> float | None:
        """Wall-clock duration in milliseconds, or None if not yet complete."""
        if self.completed_at is None:
            return None
        delta = self.completed_at - self.started_at
        return delta.total_seconds() * 1000.0

    def to_summary(self) -> dict[str, Any]:
        """Return a lightweight summary dict suitable for logging."""
        return {
            "session_id": self.session_id,
            "input_len": len(self.user_input),
            "memories_retrieved": len(self.retrieved_memories),
            "tools_called": len(self.selected_tools),
            "tool_results": len(self.tool_results),
            "response_len": len(self.final_response),
            "elapsed_ms": self.elapsed_ms,
            "error": self.error,
        }