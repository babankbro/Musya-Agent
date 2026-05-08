"""Centralized Agent defaults and 429-aware crew kickoff helper.

Usage:
    from src.agents.agent_defaults import agent_retry_kwargs, kickoff_with_retry
    Agent(..., **agent_retry_kwargs())
    result = kickoff_with_retry(crew)
"""
import logging
import time
import asyncio

from src.config import get_settings

logger = logging.getLogger(__name__)


def _patch_gemini_429_backoff() -> None:
    """Monkey-patch CrewAI Agent._handle_execution_error to sleep on 429 before retrying.

    _handle_execution_error is the exact point where CrewAI calls execute_task
    again after an error. Injecting a sleep here for 429 errors ensures every
    retry waits GEMINI_RETRY_DELAY seconds for the rate limit window to clear.
    The patch is idempotent — calling it multiple times is safe.
    """
    try:
        from crewai.agent.core import Agent as CrewAgent
    except ImportError:
        logger.debug("crewai.agent.core.Agent not found — skipping 429 backoff patch")
        return

    if getattr(CrewAgent, "_429_patched", False):
        return

    _original_handle = CrewAgent._handle_execution_error
    _original_handle_async = CrewAgent._handle_execution_error_async

    def _get_delay(agent_instance):
        base_delay = get_settings().GEMINI_RETRY_DELAY
        attempt = getattr(agent_instance, "_times_executed", 0)
        max_retries = getattr(agent_instance, "max_retry_limit", 5)
        # Exponential backoff: base * 2^attempt, capped at 300s
        delay = min(base_delay * (2 ** attempt), 300)
        logger.warning(
            "429 RESOURCE_EXHAUSTED — sleeping %ds before CrewAI agent retry (attempt %d/%d)",
            delay,
            attempt + 1,
            max_retries + 1,
        )
        return delay

    def _patched_handle(self, e, task, context, tools):
        err = str(e)
        if "429" in err or "RESOURCE_EXHAUSTED" in err:
            time.sleep(_get_delay(self))
        return _original_handle(self, e, task, context, tools)

    async def _patched_handle_async(self, e, task, context, tools):
        err = str(e)
        if "429" in err or "RESOURCE_EXHAUSTED" in err:
            await asyncio.sleep(_get_delay(self))
        return await _original_handle_async(self, e, task, context, tools)

    CrewAgent._handle_execution_error = _patched_handle
    CrewAgent._handle_execution_error_async = _patched_handle_async
    CrewAgent._429_patched = True
    logger.info("CrewAI Agent._handle_execution_error(sync/async) 429 backoff patch applied")


_patch_gemini_429_backoff()


def agent_retry_kwargs() -> dict:
    """Return retry kwargs for CrewAI Agent() constructors.

    Only max_retry_limit is a valid Agent field in CrewAI 1.13.0.
    """
    s = get_settings()
    return {
        "max_retry_limit": s.GEMINI_RETRY_LIMIT,
    }


def kickoff_with_retry(crew, max_attempts: int = 3, delay_seconds: int = 60):
    """Run crew.kickoff() with automatic retry on 429 RESOURCE_EXHAUSTED.

    Waits delay_seconds between attempts. On final failure, re-raises.
    """
    s = get_settings()
    delay = s.GEMINI_RETRY_DELAY
    for attempt in range(1, max_attempts + 1):
        try:
            return crew.kickoff()
        except Exception as e:
            err = str(e)
            if ("429" in err or "RESOURCE_EXHAUSTED" in err) and attempt < max_attempts:
                logger.warning(
                    "429 RESOURCE_EXHAUSTED on attempt %d/%d — sleeping %ds before retry",
                    attempt, max_attempts, delay,
                )
                time.sleep(delay)
            else:
                raise
