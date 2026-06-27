"""
Context builder for the Synapse agent reasoning cycle.

The ContextBuilder assembles the structured prompt context that is
sent to the LLM during the reasoning step.  It combines:
- The agent system persona
- Retrieved relevant memories
- Tool execution results (if any)
- The planning output
- The conversation history
- The user's current input
"""

from __future__ import annotations

from app.core.logger import get_logger
from app.schemas.chat import ChatMessage
from app.schemas.memory import MemorySearchResult
from app.schemas.tool import ToolResult

logger = get_logger(__name__)

_SYSTEM_PERSONA = """\
You are Synapse, an advanced autonomous AI assistant with long-term memory,
multi-step reasoning, and the ability to use tools.

Core behaviour:
- Reason step by step before answering.
- Use memory context when relevant to personalise responses.
- Cite tool results when they inform your answer.
- Be clear, concise, and helpful.
- If you are unsure, say so rather than fabricating information.
"""


class ContextBuilder:
    """
    Builds the full prompt context for the LLM reasoning step.

    This class is stateless; call `build()` for each reasoning cycle.
    """

    def build(
        self,
        user_input: str,
        plan: dict,
        memories: list[MemorySearchResult],
        tool_results: list[ToolResult],
        conversation_history: list[ChatMessage],
    ) -> tuple[str, list[dict[str, str]]]:
        """
        Assemble the system prompt and message list for the reasoning call.

        Args:
            user_input:           Current user message text.
            plan:                 Structured plan from the Planner.
            memories:             Retrieved memory records with scores.
            tool_results:         Results from pre-reasoning tool executions.
            conversation_history: Prior conversation turns.

        Returns:
            A tuple of (system_prompt, messages_list).
        """
        system_parts: list[str] = [_SYSTEM_PERSONA]

        # Inject retrieved memories
        if memories:
            system_parts.append(self._format_memories(memories))

        # Inject tool results
        if tool_results:
            system_parts.append(self._format_tool_results(tool_results))

        # Inject plan
        system_parts.append(self._format_plan(plan))

        system_prompt = "\n\n---\n\n".join(system_parts)

        # Build the message list
        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
        ]

        # Add recent conversation history (last 10 turns)
        for msg in conversation_history[-10:]:
            messages.append({"role": msg.role, "content": msg.content})

        logger.debug(
            "build() — memories={} tools={} history_turns={} system_len={}",
            len(memories),
            len(tool_results),
            len(conversation_history),
            len(system_prompt),
        )
        return system_prompt, messages

    @staticmethod
    def _format_memories(memories: list[MemorySearchResult]) -> str:
        """Format retrieved memories into a readable context block."""
        lines = ["## Relevant Memories"]
        for i, m in enumerate(memories, start=1):
            tags = ", ".join(m.record.tags) if m.record.tags else "none"
            lines.append(
                f"{i}. [score={m.score:.2f} | tags={tags}] {m.record.text}"
            )
        return "\n".join(lines)

    @staticmethod
    def _format_tool_results(results: list[ToolResult]) -> str:
        """Format tool execution results into a readable context block."""
        lines = ["## Tool Results"]
        for r in results:
            if r.status.value == "success":
                lines.append(f"- {r.tool_name}: {r.output}")
            else:
                lines.append(f"- {r.tool_name}: ERROR — {r.error}")
        return "\n".join(lines)

    @staticmethod
    def _format_plan(plan: dict) -> str:
        """Format the planning output into a context block."""
        steps = plan.get("steps", [])
        step_text = "\n".join(f"  {i + 1}. {s}" for i, s in enumerate(steps))
        return (
            f"## Current Plan\n"
            f"Intent: {plan.get('intent', '')}\n"
            f"Steps:\n{step_text}"
        )