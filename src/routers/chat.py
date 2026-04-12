"""Chat endpoint — main entry point for ChatV1 frontend."""
import logging
import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from src.schemas.request import ChatRequest
from src.schemas.response import AgentResponse
from src.agents.orchestrator import run_chat

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


@router.post("/api/chat", response_model=AgentResponse)
async def chat(request: ChatRequest):
    """Process a chat message through the agent pipeline.
    
    Returns a structured AgentResponse with content, charts, tables, citations.
    """
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    logger.info(f"Chat request: {request.message[:100]}... (session: {request.session_id})")

    try:
        response = run_chat(
            user_message=request.message,
            session_id=request.session_id,
        )
        return response
    except Exception as e:
        logger.error(f"Chat processing failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Agent processing failed: {str(e)}")


@router.post("/api/chat/stream")
async def chat_stream(request: ChatRequest):
    """Stream chat response via Server-Sent Events (SSE).
    
    Sends partial results as they become available.
    For Phase 1, this wraps the synchronous crew result in SSE format.
    """
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    async def event_generator():
        try:
            # Send start event
            yield f"data: {json.dumps({'type': 'start', 'message': 'กำลังประมวลผล...'})}\n\n"

            # Run the crew (synchronous in Phase 1)
            response = run_chat(
                user_message=request.message,
                session_id=request.session_id,
            )

            # Send the full response
            yield f"data: {json.dumps({'type': 'content', 'data': response.model_dump()}, ensure_ascii=False)}\n\n"

            # Send done event
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            logger.error(f"Stream failed: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
