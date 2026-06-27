"""
WebSocket endpoint for streaming agent responses in Synapse.

Clients connect and send a JSON message describing the chat request.
The server runs the agent pipeline and streams the final response
token by token via the WebSocket connection.

Protocol (client → server):
    {
        "user_input": "What is the weather like?",
        "session_id": "<optional-uuid>",
        "use_memory": true,
        "history": [
            {"role": "user", "content": "..."},
            {"role": "assistant", "content": "..."}
        ]
    }

Protocol (server → client, streamed):
    {"type": "chunk",  "content": "Partial text..."}
    {"type": "done",   "session_id": "...", "error": null}
    {"type": "error",  "content": "Error description"}
"""

from __future__ import annotations

import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.agent.cycle import AgentCycle
from app.api.dependencies import get_agent_cycle
from app.core.logger import get_logger
from app.schemas.chat import ChatMessage

logger = get_logger(__name__)

ws_router = APIRouter()


@ws_router.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket) -> None:
    """
    WebSocket endpoint for streaming agent responses.

    Accepts a single JSON message per connection describing the chat
    request, then streams the response back as a series of JSON frames.
    """
    await websocket.accept()
    logger.info("WebSocket connection accepted — client={}", websocket.client)

    cycle: AgentCycle = get_agent_cycle()

    try:
        raw = await websocket.receive_text()
        request = _parse_request(raw)

        if request is None:
            await websocket.send_text(
                json.dumps({"type": "error", "content": "Invalid request format."})
            )
            await websocket.close(code=1003)
            return

        user_input: str = request["user_input"]
        session_id: str | None = request.get("session_id")
        use_memory: bool = request.get("use_memory", True)
        history_raw: list[dict] = request.get("history", [])
        history = [ChatMessage(**m) for m in history_raw]

        logger.info(
            "WebSocket /ws/chat — session={} input_len={} use_memory={}",
            session_id,
            len(user_input),
            use_memory,
        )

        async for chunk in cycle.stream(
            user_input=user_input,
            conversation_history=history,
            session_id=session_id,
            use_memory=use_memory,
        ):
            await websocket.send_text(
                json.dumps({"type": "chunk", "content": chunk})
            )

        await websocket.send_text(
            json.dumps(
                {
                    "type": "done",
                    "session_id": session_id or "",
                    "error": None,
                }
            )
        )

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected — client={}", websocket.client)
    except Exception as exc:
        logger.exception("WebSocket error: {}", exc)
        try:
            await websocket.send_text(
                json.dumps({"type": "error", "content": str(exc)})
            )
        except Exception:
            pass  # Connection may already be closed


def _parse_request(raw: str) -> dict | None:
    """
    Parse and validate the incoming WebSocket JSON request.

    Args:
        raw: Raw JSON string from the client.

    Returns:
        Parsed dict if valid, None otherwise.
    """
    try:
        data = json.loads(raw)
        if not isinstance(data, dict) or "user_input" not in data:
            return None
        if not isinstance(data["user_input"], str) or not data["user_input"].strip():
            return None
        return data
    except json.JSONDecodeError:
        return None