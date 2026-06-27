"""
FastAPI dependency providers for Synapse.
"""

from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv

from app.agent.cycle import AgentCycle
from app.agent.tools import build_default_registry
from app.core.llm_client import LLMClient
from app.core.memory import MemoryService
from app.core.workflow import WorkflowClient

load_dotenv()


@lru_cache(maxsize=1)
def get_memory_service() -> MemoryService:
    return MemoryService(
        qdrant_url=os.getenv("QDRANT_URL", "http://localhost:6333"),
        collection=os.getenv("QDRANT_COLLECTION", "synapse_memory"),
    )


@lru_cache(maxsize=1)
def get_llm_client() -> LLMClient:
    return LLMClient()


@lru_cache(maxsize=1)
def get_tool_registry():
    return build_default_registry()


@lru_cache(maxsize=1)
def get_workflow_client() -> WorkflowClient:
    """
    Return a singleton WorkflowClient instance.
    """
    return WorkflowClient()


@lru_cache(maxsize=1)
def get_agent_cycle() -> AgentCycle:
    return AgentCycle(
        memory=get_memory_service(),
        llm=get_llm_client(),
        tools=get_tool_registry(),
    )