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

from langfuse import (
    observe,
    get_client,
    propagate_attributes,
)


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
    "flush_langfuse",
    "shutdown_langfuse",
    "update_current_observation_safe",
    "update_current_generation_safe",
]