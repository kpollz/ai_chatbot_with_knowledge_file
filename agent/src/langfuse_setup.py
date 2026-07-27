"""Langfuse v4 tracing for the agent.

Tracing is opt-in: with no keys in the environment every function here is a
no-op and the agent runs untraced.

The handler is attached once, to the config the AG-UI agent passes into each run
(``main.py``), so every LLM call and tool step of the ReAct loop shows up as
nested observations.
"""

import atexit

from langfuse import get_client

from src.config import LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY
from src.logger import logger


def is_configured() -> bool:
    """True when Langfuse keys are present. Tracing is a no-op otherwise."""
    return bool(LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY)


def langchain_handler():
    """LangChain/LangGraph CallbackHandler for tracing agent runs, or None if off."""
    if not is_configured():
        return None
    try:
        from langfuse.langchain import CallbackHandler
        return CallbackHandler()
    except Exception as exc:  # never let tracing break a run
        logger.warning(f"langfuse langchain handler unavailable: {exc}")
        return None


def flush_langfuse() -> None:
    """Drain the queue. Called once at exit, never per request.

    The SDK's background exporter sends traces off the request path during
    normal operation; a synchronous flush per request would add a blocking
    round-trip to the tail of every answer.
    """
    client = get_client()
    if client:
        client.flush()


def _flush_at_exit() -> None:
    try:
        flush_langfuse()
    except Exception:
        pass


atexit.register(_flush_at_exit)
