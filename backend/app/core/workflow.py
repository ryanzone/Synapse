"""
n8n workflow client for Synapse backend.

Provides a clean async interface for interacting with the n8n workflow
automation engine via its REST API.

Supports:
- Listing available workflows
- Executing a workflow by ID
- Polling workflow execution status
"""

from __future__ import annotations

from typing import Any, Optional

import httpx

from app.core.config import Settings, get_settings
from app.core.logger import get_logger
from app.schemas.workflow import WorkflowExecution, WorkflowInfo, WorkflowStatus

logger = get_logger(__name__)

_REQUEST_TIMEOUT = 30.0  # seconds


class WorkflowClient:
    """
    Async HTTP client for the n8n workflow engine REST API.

    Args:
        settings: Application settings.  Defaults to the global singleton.
    """

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self._settings = settings or get_settings()
        self._base_url = self._settings.n8n_url.rstrip("/")
        self._headers: dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self._settings.n8n_api_key:
            self._headers["X-N8N-API-KEY"] = self._settings.n8n_api_key

        logger.info("WorkflowClient initialised — n8n_url={}", self._base_url)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def list_workflows(self) -> list[WorkflowInfo]:
        """
        Retrieve all workflows registered in n8n.

        Returns:
            List of WorkflowInfo objects sorted by name ascending.

        Raises:
            httpx.HTTPStatusError: On non-2xx responses.
        """
        async with self._make_client() as client:
            response = await client.get("/api/v1/workflows")
            response.raise_for_status()
            data: dict[str, Any] = response.json()

        workflows = [
            WorkflowInfo(
                id=str(w["id"]),
                name=w.get("name", ""),
                active=w.get("active", False),
                tags=[t.get("name", "") for t in w.get("tags", [])],
            )
            for w in data.get("data", [])
        ]
        workflows.sort(key=lambda w: w.name.lower())
        logger.debug("list_workflows() — count={}", len(workflows))
        return workflows

    async def execute_workflow(
        self,
        workflow_id: str,
        input_data: dict[str, Any] | None = None,
    ) -> WorkflowExecution:
        """
        Trigger execution of a workflow by its ID.

        Args:
            workflow_id: n8n workflow UUID or integer ID as a string.
            input_data:  Optional JSON payload forwarded to the workflow's
                         webhook / trigger node.

        Returns:
            WorkflowExecution describing the triggered execution.

        Raises:
            httpx.HTTPStatusError: On non-2xx responses.
        """
        body: dict[str, Any] = {"workflowData": input_data or {}}

        async with self._make_client() as client:
            response = await client.post(
                f"/api/v1/workflows/{workflow_id}/execute",
                json=body,
            )
            response.raise_for_status()
            data: dict[str, Any] = response.json()

        execution = WorkflowExecution(
            execution_id=str(data.get("data", {}).get("executionId", "")),
            workflow_id=workflow_id,
            status=WorkflowStatus.RUNNING,
            data=data.get("data", {}),
        )
        logger.info(
            "execute_workflow() — workflow_id={} execution_id={}",
            workflow_id,
            execution.execution_id,
        )
        return execution

    async def get_execution_status(
        self, execution_id: str
    ) -> WorkflowExecution:
        """
        Poll the status of a specific workflow execution.

        Args:
            execution_id: The execution ID returned by execute_workflow().

        Returns:
            Updated WorkflowExecution with current status.

        Raises:
            httpx.HTTPStatusError: On non-2xx responses.
        """
        async with self._make_client() as client:
            response = await client.get(
                f"/api/v1/executions/{execution_id}"
            )
            response.raise_for_status()
            data: dict[str, Any] = response.json()

        raw_status: str = (
            data.get("data", {}).get("status", "unknown").lower()
        )
        status_map = {
            "running": WorkflowStatus.RUNNING,
            "success": WorkflowStatus.SUCCESS,
            "error": WorkflowStatus.ERROR,
            "waiting": WorkflowStatus.WAITING,
            "canceled": WorkflowStatus.CANCELED,
        }
        status = status_map.get(raw_status, WorkflowStatus.UNKNOWN)

        execution = WorkflowExecution(
            execution_id=execution_id,
            workflow_id=str(
                data.get("data", {}).get("workflowId", "")
            ),
            status=status,
            data=data.get("data", {}),
        )
        logger.debug(
            "get_execution_status() — execution_id={} status={}",
            execution_id,
            status,
        )
        return execution

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _make_client(self) -> httpx.AsyncClient:
        """Create a configured AsyncClient for a single request block."""
        return httpx.AsyncClient(
            base_url=self._base_url,
            headers=self._headers,
            timeout=_REQUEST_TIMEOUT,
        )