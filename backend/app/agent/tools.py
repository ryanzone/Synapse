"""
Tool registry and built-in tool implementations for the Synapse agent.

Tools are registered with a ToolRegistry and invoked by name from the
agent executor.  Each tool is an async callable accepting a parameter
dict and returning any JSON-serialisable value.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from app.core.logger import get_logger
from app.schemas.tool import ToolCall, ToolDefinition, ToolResult, ToolStatus

logger = get_logger(__name__)

ToolHandler = Callable[[dict[str, Any]], Awaitable[Any]]


class ToolRegistry:
    """
    Registry that maps tool names to their handler coroutines and definitions.

    Tools are registered via the `register` decorator or `add` method and
    are looked up by name during execution.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, ToolHandler] = {}
        self._definitions: dict[str, ToolDefinition] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any] | None = None,
    ) -> Callable[[ToolHandler], ToolHandler]:
        """
        Decorator that registers a coroutine as a named tool.

        Args:
            name:        Unique tool identifier.
            description: Human-readable description.
            parameters:  JSON Schema dict describing the tool parameters.

        Returns:
            Decorator function.
        """
        def decorator(fn: ToolHandler) -> ToolHandler:
            self.add(fn, name=name, description=description, parameters=parameters or {})
            return fn
        return decorator

    def add(
        self,
        handler: ToolHandler,
        *,
        name: str,
        description: str,
        parameters: dict[str, Any],
    ) -> None:
        """
        Register a handler directly (non-decorator form).

        Args:
            handler:     Async callable to invoke.
            name:        Tool name.
            description: Human-readable description.
            parameters:  JSON Schema for parameters.
        """
        if name in self._handlers:
            raise ValueError(f"A tool named '{name}' is already registered.")
        self._handlers[name] = handler
        self._definitions[name] = ToolDefinition(
            name=name,
            description=description,
            parameters=parameters,
        )
        logger.debug("Registered tool '{}'", name)

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def get_definitions(self) -> list[ToolDefinition]:
        """Return all registered tool definitions."""
        return list(self._definitions.values())


    def list_tools(self) -> list[dict[str, Any]]:
        """Return tool definitions as dictionaries."""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            }
            for tool in self._definitions.values()
        ]
    

    def has_tool(self, name: str) -> bool:
        """Check whether a tool with the given name is registered."""
        return name in self._handlers
    

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def execute(self, call: ToolCall) -> ToolResult:
        """
        Execute a single tool call and return its result.

        Args:
            call: The ToolCall specifying which tool to run and with what params.

        Returns:
            ToolResult with status, output, and timing.
        """
        if not self.has_tool(call.tool_name):
            logger.warning("execute() — unknown tool '{}'", call.tool_name)
            return ToolResult(
                tool_name=call.tool_name,
                status=ToolStatus.ERROR,
                error=f"No tool named '{call.tool_name}' is registered.",
            )

        handler = self._handlers[call.tool_name]
        start = time.perf_counter()

        try:
            output = await handler(call.parameters)
            duration_ms = (time.perf_counter() - start) * 1000.0
            logger.info(
                "execute() — tool='{}' duration_ms={:.1f}",
                call.tool_name,
                duration_ms,
            )
            return ToolResult(
                tool_name=call.tool_name,
                status=ToolStatus.SUCCESS,
                output=output,
                duration_ms=duration_ms,
            )
        except Exception as exc:
            duration_ms = (time.perf_counter() - start) * 1000.0
            logger.exception(
                "execute() — tool='{}' raised {}", call.tool_name, exc
            )
            return ToolResult(
                tool_name=call.tool_name,
                status=ToolStatus.ERROR,
                error=str(exc),
                duration_ms=duration_ms,
            )


# ---------------------------------------------------------------------------
# Default built-in tools
# ---------------------------------------------------------------------------

def build_default_registry() -> ToolRegistry:
    """
    Construct and return the default ToolRegistry with built-in tools.

    Returns:
        Populated ToolRegistry instance.
    """
    registry = ToolRegistry()

    # --- current_time -------------------------------------------------------
    async def current_time(_params: dict[str, Any]) -> dict[str, str]:
        """Return the current UTC time."""
        now = datetime.now(tz=timezone.utc)
        return {
            "utc_iso": now.isoformat(),
            "utc_human": now.strftime("%Y-%m-%d %H:%M:%S UTC"),
        }

    registry.add(
        current_time,
        name="current_time",
        description="Returns the current UTC date and time.",
        parameters={},
    )

    # --- calculate ----------------------------------------------------------
    async def calculate(params: dict[str, Any]) -> dict[str, Any]:
        """
        Safely evaluate a simple arithmetic expression.

        Accepts:
            expression (str): A Python arithmetic expression using only
                              numbers and the operators + - * / ** ( ).
        """
        expression: str = str(params.get("expression", "")).strip()
        # Restrict to safe characters only
        allowed = set("0123456789+-*/()%. \t")
        if not expression or not all(c in allowed for c in expression):
            raise ValueError(
                f"Invalid expression. Only arithmetic operators and numbers are permitted. "
                f"Got: {expression!r}"
            )
        result = eval(expression, {"__builtins__": {}})  # noqa: S307
        return {"expression": expression, "result": result}

    registry.add(
        calculate,
        name="calculate",
        description=(
            "Evaluates a simple arithmetic expression and returns the result. "
            "Supports +, -, *, /, **, (, ) and numeric literals."
        ),
        parameters={
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Arithmetic expression to evaluate.",
                }
            },
            "required": ["expression"],
        },
    )

    # --- sleep (testing / delay tool) ---------------------------------------
    async def sleep_tool(params: dict[str, Any]) -> dict[str, float]:
        """Pause execution for a specified number of seconds (max 10)."""
        seconds = min(float(params.get("seconds", 1.0)), 10.0)
        await asyncio.sleep(seconds)
        return {"slept_seconds": seconds}

    registry.add(
        sleep_tool,
        name="sleep",
        description="Pauses agent execution for a specified number of seconds. Useful for testing.",
        parameters={
            "type": "object",
            "properties": {
                "seconds": {
                    "type": "number",
                    "description": "Duration to sleep in seconds (capped at 10).",
                }
            },
        },
    )

    return registry