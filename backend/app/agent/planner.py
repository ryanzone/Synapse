"""
Planner stage of the Synapse agent reasoning cycle.

The Planner uses the LLM to decompose the user's input into a structured
plan that guides the rest of the pipeline:
- Clarified intent
- List of steps required
- Required tools
- Memory search query
"""

from __future__ import annotations

import json
from typing import Any

from app.core.llm_client import LLMClient
from app.core.logger import get_logger
from app.schemas.tool import ToolDefinition

logger = get_logger(__name__)

_PLANNER_SYSTEM_PROMPT = """\
You are the Planner component of an autonomous AI system called Synapse.

Your job is to analyse the user's latest message and produce a structured
reasoning plan in JSON.  Output ONLY valid JSON — no markdown fences,
no explanation text, just the raw JSON object.

The JSON object must have these fields:
{
  "intent": "<one sentence describing what the user wants>",
  "steps": ["<step 1>", "<step 2>", ...],
  "required_tools": ["<tool_name>", ...],
  "memory_query": "<concise phrase to search long-term memory>",
  "needs_vision": false,
  "complexity": "low|medium|high"
}

Rules:
- "required_tools" must only contain tool names from the provided list.
- "memory_query" should be the most relevant phrase for semantic search.
- "needs_vision" is true only when the user explicitly mentions an image.
- Be concise but complete.
"""


class Planner:
    """
    Produces a structured plan from the user's input and available tools.

    Args:
        llm_client: LLMClient instance.
    """

    def __init__(self, llm_client: LLMClient) -> None:
        self._llm = llm_client

    async def plan(
        self,
        user_input: str,
        conversation_history: list[dict[str, str]],
        available_tools: list[ToolDefinition],
    ) -> dict[str, Any]:
        """
        Generate a reasoning plan for the given user input.

        Args:
            user_input:           The latest user message.
            conversation_history: Prior turns for context.
            available_tools:      Tools the agent may invoke.

        Returns:
            Parsed plan dict with keys: intent, steps, required_tools,
            memory_query, needs_vision, complexity.
        """
        tool_names = [t.name for t in available_tools]
        tool_list_text = ", ".join(tool_names) if tool_names else "none"

        user_message = (
            f"Available tools: [{tool_list_text}]\n\n"
            f"User message: {user_input}"
        )

        messages: list[dict[str, str]] = [
            {"role": "system", "content": _PLANNER_SYSTEM_PROMPT},
            *conversation_history[-6:],  # Last 3 turns for context
            {"role": "user", "content": user_message},
        ]

        raw = await self._llm.chat(messages=messages, temperature=0.3, max_tokens=512)
        logger.debug("Planner raw output: {}", raw[:200])

        plan = self._parse_plan(raw)
        logger.info(
            "plan() — intent='{}' steps={} tools={}",
            plan.get("intent", "")[:60],
            len(plan.get("steps", [])),
            plan.get("required_tools", []),
        )
        return plan

    @staticmethod
    def _parse_plan(raw: str) -> dict[str, Any]:
        """
        Parse JSON from the LLM output, with fallback defaults.

        Args:
            raw: Raw string output from the LLM.

        Returns:
            Parsed plan dict.  Falls back to a minimal safe plan on errors.
        """
        try:
            # Strip possible markdown fences if the model adds them
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                lines = cleaned.splitlines()
                cleaned = "\n".join(
                    l for l in lines if not l.strip().startswith("```")
                )
            return json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning("Planner could not parse JSON; using fallback plan.")
            return {
                "intent": "Respond to the user's request.",
                "steps": ["Analyse the request", "Generate a response"],
                "required_tools": [],
                "memory_query": raw[:100],
                "needs_vision": False,
                "complexity": "low",
            }