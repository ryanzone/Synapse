"""
FastAPI HTTP route definitions for Synapse.

Endpoints:
    GET  /              — Service info
    GET  /health        — Health check
    POST /chat          — Chat with the agent
    POST /memory/store  — Store a memory
    POST /memory/search — Semantic memory search
    POST /workflow/run  — Execute an n8n workflow
    GET  /workflow/list — List available n8n workflows
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
import time

from app.agent.cycle import AgentCycle
from app.api.dependencies import (
    get_agent_cycle,
    get_memory_service,
    get_workflow_client,
)
from app.core.logger import get_logger
from app.core.memory import MemoryService
from app.core.workflow import WorkflowClient
from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.memory import (
    MemoryRecord,
    MemorySearchResult,
    SearchMemoryRequest,
    StoreMemoryRequest,
)
from app.schemas.workflow import RunWorkflowRequest, WorkflowExecution, WorkflowInfo

logger = get_logger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Service metadata
# ---------------------------------------------------------------------------

@router.get("/", summary="Service root")
async def root() -> dict:
    """Return basic service identification information."""
    return {
        "service": "Synapse",
        "version": "1.0.0",
        "description": "Autonomous AI platform — backend API",
    }


@router.get("/health", summary="Health check")
async def health() -> dict:
    """Return service health status."""
    return {
        "status": "ok",
        "service": "Synapse",
        "version": "1.0.0",
    }


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------

@router.post("/chat", response_model=ChatResponse, summary="Chat with the agent")
async def chat(
    request: ChatRequest,
    cycle: AgentCycle = Depends(get_agent_cycle),
) -> ChatResponse:
    """
    Submit a conversation to the agent and receive a response.

    The agent runs the full pipeline: plan → memory → reason → tools →
    reflect → synthesise → store.
    """
    logger.info(
        "POST /chat — turns={} use_memory={} model={}",
        len(request.messages),
        request.use_memory,
        request.model or "default",
    )
    start = time.perf_counter()
    try:
        state = await cycle.run(
            user_goal=request.messages[-1].content,
        )
    except Exception as exc:
        logger.exception("Agent execution failed: {}", exc)
        raise HTTPException(status_code=500, detail=str(exc))

    end = time.perf_counter()
    logger.info("POST /chat — latency={:.2f}ms", (end - start) * 1000)

    return ChatResponse(
        reply=state["final_response"],
        model=request.model or "default",
        memory_ids=[],
        metadata=state,
    )

# ---------------------------------------------------------------------------
# Memory
# ---------------------------------------------------------------------------

@router.post(
    "/memory/store",
    response_model=MemoryRecord,
    summary="Store a memory",
)
async def store_memory(
    request: StoreMemoryRequest,
    memory: MemoryService = Depends(get_memory_service),
) -> MemoryRecord:
    """Embed and persist a new memory record to Qdrant."""
    logger.info("POST /memory/store — text_len={}", len(request.text))
    try:
        return await memory.store_memory(
            text=request.text,
            metadata=request.metadata,
            importance=request.importance,
            tags=request.tags,
        )
    except Exception as exc:
        logger.exception("store_memory failed: {}", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post(
    "/memory/search",
    response_model=list[MemorySearchResult],
    summary="Semantic memory search",
)
async def search_memory(
    request: SearchMemoryRequest,
    memory: MemoryService = Depends(get_memory_service),
) -> list[MemorySearchResult]:
    """Search long-term memory using semantic similarity."""
    logger.info("POST /memory/search — query_len={}", len(request.query))
    try:
        return await memory.search_memory(
            query=request.query,
            limit=request.limit,
            score_threshold=request.score_threshold,
            tag_filter=request.tag_filter,
        )
    except Exception as exc:
        logger.exception("search_memory failed: {}", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get(
    "/memory/recent",
    response_model=list[MemoryRecord],
    summary="List recent memories",
)
async def list_recent_memories(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    memory: MemoryService = Depends(get_memory_service),
) -> list[MemoryRecord]:
    """Return the most recently stored memory records."""
    try:
        return await memory.list_recent(limit=limit, offset=offset)
    except Exception as exc:
        logger.exception("list_recent failed: {}", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Workflow
# ---------------------------------------------------------------------------
@router.get(
    "/workflow/list",
    response_model=list[WorkflowInfo],
    summary="List available workflows",
)
async def list_workflows(
    workflow_client: WorkflowClient = Depends(get_workflow_client),
) -> list[WorkflowInfo]:
    """Return all workflows registered in n8n."""
    try:
        return await workflow_client.list_workflows()
    
    except Exception as exc:
        logger.exception("list_workflows failed: {}", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post(
    "/workflow/run",
    response_model=WorkflowExecution,
    summary="Execute a workflow",
)
async def run_workflow(
    request: RunWorkflowRequest,
    workflow_client: WorkflowClient = Depends(get_workflow_client),
) -> WorkflowExecution:
    """Trigger execution of an n8n workflow by ID."""
    logger.info("POST /workflow/run — workflow_id={}", request.workflow_id)
    try:
        return await workflow_client.execute_workflow(
            workflow_id=request.workflow_id,
            input_data=request.input_data,
        )
    except Exception as exc:
        logger.exception("run_workflow failed: {}", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc

@router.get(
    "/workflow/status/{execution_id}",
    response_model=WorkflowExecution,
    summary="Workflow execution status",
)

async def workflow_status(
    execution_id: str,
    workflow_client: WorkflowClient = Depends(get_workflow_client),
) -> WorkflowExecution:
    """Poll the status of a running workflow execution."""
    logger.info("GET /workflow/status — execution_id={}", execution_id)
    try:
        return await workflow_client.get_execution_status(execution_id)
    except Exception as exc:
        logger.exception("workflow_status failed: {}", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc