"""
Langfuse SDK v4 Setup and Utilities

Langfuse SDK v4 is built on OpenTelemetry and provides automatic instrumentation.
Configuration is done via environment variables:
  - LANGFUSE_PUBLIC_KEY (or LANGFUSE_PK)
  - LANGFUSE_SECRET_KEY (or LANGFUSE_SK)
  - LANGFUSE_HOST

Installation:
  pip install langfuse>=4.0.0

This module provides:
  - Re-export of common Langfuse decorators/functions
  - Utility functions for working with observations
  - Helper for flushing events (important for short-lived processes)

Basic Usage:
    from langfuse_setup import observe, get_client
    
    @observe(name="my_function")
    def my_function():
        # Inputs/outputs are auto-captured by @observe decorator
        # To update metadata on the current observation:
        client = get_client()
        client.update_current_span(metadata={"key": "value"})
        return result

Setting Trace Attributes (session_id, user_id):
    from langfuse import observe, propagate_attributes
    
    @observe()
    def my_function(session_id, user_id):
        with propagate_attributes(session_id=session_id, user_id=user_id):
            # All observations created here will have these attributes
            result = call_llm("hello")
        return result
"""

from contextlib import contextmanager

from langfuse import (
    observe,
    get_client,
    propagate_attributes,
)

from config import LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY
from logger import logger

# Flag to track if Langfuse is available and working
_langfuse_available: bool | None = None


def is_configured() -> bool:
    """True when Langfuse keys are present. Tracing is a no-op otherwise."""
    return bool(LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY)


def langchain_handler():
    """LangChain/LangGraph CallbackHandler for tracing agent runs, or None if off.

    Mirrors the chat-with-documents pattern: attach this to the LangGraph
    ``agent.stream(config={"callbacks": [handler]})`` so every LLM/tool step of
    the ReAct agent shows up as nested observations in Langfuse.
    """
    if not is_configured():
        return None
    try:
        from langfuse.langchain import CallbackHandler
        return CallbackHandler()
    except Exception as exc:  # never let tracing break chat
        logger.warning(f"langfuse langchain handler unavailable: {exc}")
        return None


@contextmanager
def trace_attributes(session_id: str = "", user_id: str = "",
                     trace_name: str = "chat_query"):
    """Set trace-level attributes (session/user/name) for the enclosed run.

    No-op when tracing is off. session_id groups a conversation's turns into
    one Langfuse trace.
    """
    if not is_configured():
        yield
        return
    try:
        with propagate_attributes(user_id=user_id or "", session_id=session_id or "",
                                  trace_name=trace_name):
            yield
    except Exception as exc:
        logger.warning(f"langfuse propagate_attributes unavailable: {exc}")
        yield


def is_langfuse_available() -> bool:
    """Check if Langfuse client is properly configured and reachable."""
    global _langfuse_available
    if _langfuse_available is not None:
        return _langfuse_available
    
    try:
        client = get_client()
        if client is None:
            _langfuse_available = False
            return False
        # Try a lightweight check - if auth fails, client will be disabled
        _langfuse_available = True
        return True
    except Exception:
        _langfuse_available = False
        return False


def reset_langfuse_status():
    """Reset the cached Langfuse availability status (e.g., after config change)."""
    global _langfuse_available
    _langfuse_available = None


def flush_langfuse(timeout: float = 30.0) -> None:
    """
    Flush all pending Langfuse events.
    
    IMPORTANT: Call this before your application exits to ensure all
    telemetry data is sent. This is especially critical for:
    - Short-lived scripts
    - Serverless functions (AWS Lambda, etc.)
    - Jupyter notebooks
    - During shutdown
    
    Args:
        timeout: Maximum time to wait for flush completion (seconds)
    """
    client = get_client()
    if client:
        client.flush(timeout=timeout)


def shutdown_langfuse(timeout: float = 30.0) -> None:
    """
    Shutdown Langfuse client gracefully.
    
    This flushes pending events and releases resources.
    Call this during application shutdown.
    
    Args:
        timeout: Maximum time to wait for shutdown (seconds)
    """
    client = get_client()
    if client:
        client.shutdown(timeout=timeout)


def update_current_observation_safe(**kwargs) -> bool:
    """
    Safely update the current span/observation if one exists.
    
    In Langfuse v4, use get_client().update_current_span() or
    get_client().update_current_generation() instead of the old
    get_current_observation() pattern.
    
    Args:
        **kwargs: Parameters to pass to update_current_span()
            Supported keys: metadata, input, output, usage_details, etc.
        
    Returns:
        True if update was attempted, False if client unavailable
    """
    try:
        client = get_client()
        if client:
            client.update_current_span(**kwargs)
            return True
    except Exception:
        pass
    return False


def update_current_generation_safe(**kwargs) -> bool:
    """
    Safely update the current generation observation if one exists.
    
    Use this for LLM call spans (generation type) to update
    model-specific attributes like usage_details.
    
    Args:
        **kwargs: Parameters to pass to update_current_generation()
            Supported keys: metadata, input, output, usage_details, model, etc.
        
    Returns:
        True if update was attempted, False if client unavailable
    """
    try:
        client = get_client()
        if client:
            client.update_current_generation(**kwargs)
            return True
    except Exception:
        pass
    return False


# Re-export commonly used items for convenience
__all__ = [
    "observe",
    "get_client",
    "propagate_attributes",
    "is_configured",
    "langchain_handler",
    "trace_attributes",
    "flush_langfuse",
    "shutdown_langfuse",
    "update_current_observation_safe",
    "update_current_generation_safe",
]