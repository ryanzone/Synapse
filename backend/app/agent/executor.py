"""
Executor stage of the Synapse agent reasoning cycle.

The Executor parses the LLM's reasoning output to identify tool calls
and invokes them via the ToolRegistry.  It returns the list of ToolResults
which are then available to the reflection and response stages.
"""

from __future__ import annotations

import json
import re

from app.agent.tools import ToolRegistry
from app.core.logger import get_logger
from app.schemas.tool import ToolCall, ToolResult

logger = get_logger(__name__)

# Pattern to capture JSON tool call blocks the LLM may emit
_TOOL_CALL_PATTERN = re.compile(
    r"<tool_call>\s*(\{.*?\})\s*</tool_call>",
    re.DOTALL | re.IGNORECASE,
)


class Executor:
    """
    Parses tool calls from LLM output and executes them.

    Args:
        registry: ToolRegistry containing all available tools.
    """

    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry

    async def execute_from_reasoning(
        self,
        reasoning_output: str,
        planned_tools: list[str],
    ) -> tuple[list[ToolCall], list[ToolResult]]:
        """
        Extract and execute any tool calls found in the LLM output.

        The LLM is expected to emit tool calls in the following XML format:
            <tool_call>{"tool_name": "...", "parameters": {...}}</tool_call>

        Any planned tools not explicitly called in the reasoning output
        are skipped with a SKIPPED status.

        Args:
            reasoning_output: Raw LLM reasoning text.
            planned_tools:    Tool names the planner requested.

        Returns:
            Tuple of (tool_calls_attempted, tool_results).
        """
        # Parse embedded tool calls from the LLM output
        tool_calls = self._parse_tool_calls(reasoning_output)

        # If no embedded calls but planner requested tools, skip them
        if not tool_calls and planned_tools:
            logger.debug(
                "execute_from_reasoning() — no calls found; planner wanted {}",
                planned_tools,
            )
            return [], []

        # Execute each parsed call
        results: list[ToolResult] = []
        for call in tool_calls:
            result = await self._registry.execute(call)
            results.append(result)

        logger.info(
            "execute_from_reasoning() — called={} succeeded={}",
            len(tool_calls),
            sum(1 for r in results if r.status.value == "success"),
        )
        return tool_calls, results

    async def execute_calls(
        self, calls: list[ToolCall]
    ) -> list[ToolResult]:
        """
        Execute an explicit list of ToolCall objects.

        Args:
            calls: Tool calls to execute in order.

        Returns:
            List of ToolResult objects, one per call.
        """
        results: list[ToolResult] = []
        for call in calls:
            result = await self._registry.execute(call)
            results.append(result)
        return results

    @staticmethod
    def _parse_tool_calls(text: str) -> list[ToolCall]:
        """
        Extract ToolCall objects from XML-wrapped JSON blocks in the text.

        Args:
            text: Raw LLM output string.

        Returns:
            List of parsed ToolCall objects.  Invalid blocks are skipped.
        """
        calls: list[ToolCall] = []
        for match in _TOOL_CALL_PATTERN.finditer(text):
            raw_json = match.group(1)
            try:
                data = json.loads(raw_json)
                call = ToolCall(
                    tool_name=data["tool_name"],
                    parameters=data.get("parameters", {}),
                )
                calls.append(call)
                logger.debug("Parsed tool call: '{}'", call.tool_name)
            except (json.JSONDecodeError, KeyError) as exc:
                logger.warning(
                    "Skipping malformed tool call block — {}: {}",
                    type(exc).__name__,
                    exc,
                )
        return calls