"""Chat endpoint — unified entry point that routes to chat or policy-brief pipeline."""
import logging
import json
import uuid
import asyncio
from dataclasses import asdict
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from src.schemas.request import ChatRequest
from src.schemas.response import AgentResponse
from src.agents.orchestrator import run_chat
from src.agents.unified_orchestrator import run_unified, run_unified_with_progress
from src.agents.progress import (
    create_progress_queue, remove_progress_queue, get_pipeline_agents
)

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


@router.post("/api/chat/unified")
async def chat_unified(request: ChatRequest):
    """Unified endpoint: auto-routes to chat or policy-brief pipeline.

    The Request Router Agent analyzes the user's message and decides
    which pipeline to use:
    - chat_pipeline → Phase 2 (7 agents, accident data)
    - policy_brief_pipeline → Phase 3 (6 agents, policy brief)

    Returns a unified response dict with pipeline_used, routing info, and result.
    """
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    logger.info(f"Unified chat: {request.message[:100]}... (session: {request.session_id})")

    try:
        result = run_unified(
            user_message=request.message,
            session_id=request.session_id,
        )
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"Unified processing failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Agent processing failed: {str(e)}")


@router.post("/api/chat/stream")
async def chat_stream(request: ChatRequest):
    """Stream chat response via Server-Sent Events (SSE).

    Emits agent progress events as each agent completes, then the final result.
    Event types:
      - start: Initial event with pipeline info
      - routing: Router decision
      - agent_progress: Agent status update (running/done/error)
      - content: Final result
      - done: Completion signal
    """
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    request_id = str(uuid.uuid4())

    async def event_generator():
        import concurrent.futures
        import queue as sync_queue

        progress_queue = create_progress_queue(request_id)

        try:
            # Send start event
            yield f"data: {json.dumps({'type': 'start', 'message': 'กำลังประมวลผล...', 'request_id': request_id})}\n\n"

            # Run unified orchestrator in a thread pool (it's sync)
            loop = asyncio.get_event_loop()
            executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

            # Start the pipeline in background
            future = loop.run_in_executor(
                executor,
                run_unified_with_progress,
                request.message,
                request.session_id,
                request_id,
            )

            # Poll for progress events while pipeline runs
            while not future.done():
                try:
                    # Check for progress events (non-blocking)
                    event = progress_queue.get_nowait()
                    yield f"data: {json.dumps({'type': 'agent_progress', 'data': asdict(event)}, ensure_ascii=False)}\n\n"
                except sync_queue.Empty:
                    pass
                await asyncio.sleep(0.1)

            # Drain remaining progress events
            while True:
                try:
                    event = progress_queue.get_nowait()
                    yield f"data: {json.dumps({'type': 'agent_progress', 'data': asdict(event)}, ensure_ascii=False)}\n\n"
                except sync_queue.Empty:
                    break

            # Get the result
            result = future.result()

            # Send routing info
            yield f"data: {json.dumps({'type': 'routing', 'data': result['routing']}, ensure_ascii=False)}\n\n"

            # Send the full response
            yield f"data: {json.dumps({'type': 'content', 'data': result['result']}, ensure_ascii=False)}\n\n"

            # Send done event
            yield f"data: {json.dumps({'type': 'done', 'pipeline': result['pipeline_used']})}\n\n"

        except Exception as e:
            logger.error(f"Stream failed: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        finally:
            remove_progress_queue(request_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
