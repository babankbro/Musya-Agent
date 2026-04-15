"""Agent Progress Tracking — emits events for UI timeline display.

This module provides a simple queue-based progress system that agents can
push events to, and the streaming endpoint can consume from.
"""
import queue
import threading
import time
from dataclasses import dataclass, asdict
from typing import Optional, Literal
from contextlib import contextmanager

# Global progress queue (per-request, keyed by request_id)
_progress_queues: dict[str, queue.Queue] = {}
_lock = threading.Lock()


@dataclass
class AgentProgress:
    """Progress event for a single agent step."""
    request_id: str
    agent_name: str
    agent_icon: str
    status: Literal["running", "done", "error"]
    message: str
    elapsed_seconds: float = 0.0
    order: int = 0  # For timeline ordering


# Agent metadata for both pipelines
CHAT_PIPELINE_AGENTS = [
    {"name": "Request Router", "icon": "🔀", "order": 0},
    {"name": "Request Interpreter", "icon": "🎯", "order": 1},
    {"name": "Retrieval Agent", "icon": "🔍", "order": 2},
    {"name": "SQL Specialist", "icon": "🗄️", "order": 3},
    {"name": "Citation & Evidence", "icon": "📚", "order": 4},
    {"name": "Accident Analyst", "icon": "📊", "order": 5},
    {"name": "Chart Builder", "icon": "📈", "order": 6},
    {"name": "Report Writer", "icon": "✍️", "order": 7},
]

POLICY_PIPELINE_AGENTS = [
    {"name": "Request Router", "icon": "🔀", "order": 0},
    # Foundation agents 1-4 (shared — same as chat pipeline)
    {"name": "Request Interpreter", "icon": "🎯", "order": 1},
    {"name": "Retrieval Agent", "icon": "�", "order": 2},  # +NLM tools for policy
    {"name": "SQL Specialist", "icon": "🗄️", "order": 3},
    {"name": "Citation & Evidence", "icon": "📚", "order": 4},
    # Policy-specific agents 5-8
    {"name": "RTI Analyst", "icon": "🚗", "order": 5},
    {"name": "Mental Health Analyst", "icon": "🧠", "order": 5},  # parallel
    {"name": "NCD Analyst", "icon": "🍎", "order": 5},            # parallel
    {"name": "Policy Report Writer", "icon": "📋", "order": 6},
]


def create_progress_queue(request_id: str) -> queue.Queue:
    """Create a new progress queue for a request."""
    with _lock:
        q = queue.Queue()
        _progress_queues[request_id] = q
        return q


def get_progress_queue(request_id: str) -> Optional[queue.Queue]:
    """Get the progress queue for a request."""
    with _lock:
        return _progress_queues.get(request_id)


def remove_progress_queue(request_id: str) -> None:
    """Remove a progress queue after request completes."""
    with _lock:
        _progress_queues.pop(request_id, None)


def emit_progress(
    request_id: str,
    agent_name: str,
    status: Literal["running", "done", "error"],
    message: str = "",
    elapsed_seconds: float = 0.0,
) -> None:
    """Emit a progress event to the queue."""
    q = get_progress_queue(request_id)
    if not q:
        return
    
    # Find agent metadata
    all_agents = CHAT_PIPELINE_AGENTS + POLICY_PIPELINE_AGENTS
    agent_meta = next((a for a in all_agents if a["name"] == agent_name), None)
    icon = agent_meta["icon"] if agent_meta else "🤖"
    order = agent_meta["order"] if agent_meta else 0
    
    event = AgentProgress(
        request_id=request_id,
        agent_name=agent_name,
        agent_icon=icon,
        status=status,
        message=message,
        elapsed_seconds=elapsed_seconds,
        order=order,
    )
    q.put(event)


@contextmanager
def track_agent(request_id: str, agent_name: str):
    """Context manager to track agent execution time."""
    start = time.time()
    emit_progress(request_id, agent_name, "running", f"กำลังทำงาน...")
    try:
        yield
        elapsed = time.time() - start
        emit_progress(request_id, agent_name, "done", "เสร็จสิ้น", elapsed)
    except Exception as e:
        elapsed = time.time() - start
        emit_progress(request_id, agent_name, "error", str(e)[:100], elapsed)
        raise


def get_pipeline_agents(pipeline: str) -> list[dict]:
    """Get agent list for a pipeline."""
    if pipeline == "policy_brief_pipeline":
        return POLICY_PIPELINE_AGENTS
    return CHAT_PIPELINE_AGENTS
