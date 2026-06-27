"""
Synapse backend smoke tests.

These tests verify the core modules import correctly and that
non-network-dependent logic works as expected.  They do NOT require
a running LM Studio, Qdrant, or n8n instance.

Run with:
    python test.py
"""

from __future__ import annotations

import asyncio
import sys
from unittest.mock import AsyncMock, MagicMock


def test_settings() -> None:
    """Verify settings load with defaults."""
    from app.core.config import get_settings

    # Clear cache to get a fresh instance
    get_settings.cache_clear()
    s = get_settings()
    assert s.lmstudio_base_url == "http://localhost:1234/v1"
    assert s.default_model == "qwen3-4b-instruct"
    assert s.qdrant_collection == "synapse_memory"
    print("  ✓ Settings")


def test_agent_state() -> None:
    """Verify AgentState initialisation and helpers."""
    from app.agent.state import AgentState

    state = AgentState(session_id="test-session", user_input="Hello")
    assert state.session_id == "test-session"
    assert state.error is None
    assert state.elapsed_ms is None

    state.mark_complete()
    assert state.completed_at is not None
    assert state.elapsed_ms is not None and state.elapsed_ms >= 0.0

    state2 = AgentState(session_id="s2", user_input="Hi")
    state2.mark_error("test error")
    assert state2.error == "test error"
    assert state2.completed_at is not None
    print("  ✓ AgentState")


def test_tool_registry() -> None:
    """Verify tool registry registration and lookup."""
    from app.agent.tools import ToolRegistry

    registry = ToolRegistry()

    async def my_tool(params: dict) -> str:
        return "result"

    registry.add(
        my_tool,
        name="my_tool",
        description="A test tool",
        parameters={},
    )
    assert registry.has_tool("my_tool")
    assert not registry.has_tool("nonexistent")
    defs = registry.get_definitions()
    assert any(d.name == "my_tool" for d in defs)
    print("  ✓ ToolRegistry")


async def test_default_tools() -> None:
    """Verify built-in tools execute correctly."""
    from app.agent.tools import build_default_registry
    from app.schemas.tool import ToolCall, ToolStatus

    registry = build_default_registry()

    # current_time
    result = await registry.execute(ToolCall(tool_name="current_time", parameters={}))
    assert result.status == ToolStatus.SUCCESS
    assert "utc_iso" in result.output

    # calculate
    result = await registry.execute(
        ToolCall(tool_name="calculate", parameters={"expression": "2 + 2"})
    )
    assert result.status == ToolStatus.SUCCESS
    assert result.output["result"] == 4

    print("  ✓ Default tools")


def test_executor_parsing() -> None:
    """Verify the Executor correctly parses embedded tool call blocks."""
    from app.agent.executor import Executor
    from app.agent.tools import ToolRegistry

    registry = ToolRegistry()
    executor = Executor(registry)

    text_with_calls = (
        'Some reasoning text.\n'
        '<tool_call>{"tool_name": "calculate", "parameters": {"expression": "3 * 7"}}</tool_call>\n'
        'More text.'
    )
    calls = executor._parse_tool_calls(text_with_calls)
    assert len(calls) == 1
    assert calls[0].tool_name == "calculate"
    assert calls[0].parameters == {"expression": "3 * 7"}

    # No calls
    empty_calls = executor._parse_tool_calls("No tool calls here.")
    assert empty_calls == []
    print("  ✓ Executor parsing")


def test_context_builder() -> None:
    """Verify ContextBuilder produces non-empty output."""
    from app.agent.context import ContextBuilder
    from app.schemas.chat import ChatMessage

    builder = ContextBuilder()
    system_prompt, messages = builder.build(
        user_input="Hello world",
        plan={"intent": "Greet the user", "steps": ["Say hello"]},
        memories=[],
        tool_results=[],
        conversation_history=[
            ChatMessage(role="user", content="Hi"),
            ChatMessage(role="assistant", content="Hello!"),
        ],
    )
    assert len(system_prompt) > 50
    assert len(messages) >= 3  # system + 2 history turns
    assert messages[0]["role"] == "system"
    print("  ✓ ContextBuilder")


def test_planner_fallback() -> None:
    """Verify Planner's JSON fallback produces a safe plan."""
    from app.agent.planner import Planner

    plan = Planner._parse_plan("this is not json {{{")
    assert "intent" in plan
    assert "steps" in plan
    assert "required_tools" in plan
    assert isinstance(plan["steps"], list)
    print("  ✓ Planner fallback")


def test_memory_schemas() -> None:
    """Verify memory Pydantic schemas validate correctly."""
    from app.schemas.memory import MemoryRecord, MemorySearchResult

    record = MemoryRecord(
        id="abc-123",
        text="Test memory",
        importance=0.8,
        tags=["  TEST  ", "topic"],
    )
    assert record.tags == ["test", "topic"]

    result = MemorySearchResult(record=record, score=0.95)
    assert result.score == 0.95
    print("  ✓ Memory schemas")


def test_workflow_schemas() -> None:
    """Verify workflow Pydantic schemas."""
    from app.schemas.workflow import WorkflowExecution, WorkflowInfo, WorkflowStatus

    info = WorkflowInfo(id="1", name="My Flow", active=True)
    assert info.name == "My Flow"

    execution = WorkflowExecution(
        execution_id="exec-1",
        workflow_id="1",
        status=WorkflowStatus.RUNNING,
    )
    assert execution.status == WorkflowStatus.RUNNING
    print("  ✓ Workflow schemas")


async def run_async_tests() -> None:
    await test_default_tools()


def main() -> None:
    print("Running Synapse backend smoke tests…\n")

    tests = [
        test_settings,
        test_agent_state,
        test_tool_registry,
        test_executor_parsing,
        test_context_builder,
        test_planner_fallback,
        test_memory_schemas,
        test_workflow_schemas,
    ]

    failed = 0
    for test_fn in tests:
        try:
            test_fn()
        except Exception as exc:
            print(f"  ✗ {test_fn.__name__}: {exc}")
            failed += 1

    # Async tests
    try:
        asyncio.run(run_async_tests())
    except Exception as exc:
        print(f"  ✗ async tests: {exc}")
        failed += 1

    print(f"\n{'All tests passed!' if failed == 0 else f'{failed} test(s) failed.'}")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()