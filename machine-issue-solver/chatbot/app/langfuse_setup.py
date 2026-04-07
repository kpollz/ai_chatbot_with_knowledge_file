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
    from langfuse_setup import observe, get_current_observation
    
    @observe(name="my_function")
    def my_function():
        obs = get_current_observation()
        if obs:
            obs.update(metadata={"key": "value"})
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
    get_current_observation,
    get_current_trace,
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
    Safely update the current observation if one exists.
    
    This is a convenience wrapper that handles the case where
    no observation is active (e.g., Langfuse not configured).
    
    Args:
        **kwargs: Parameters to pass to observation.update()
        
    Returns:
        True if update was successful, False if no active observation
    """
    obs = get_current_observation()
    if obs:
        obs.update(**kwargs)
        return True
    return False


def set_trace_attributes(session_id: str = None, user_id: str = None, **kwargs) -> bool:
    """
    Set trace attributes using propagate_attributes context manager.
    
    In Langfuse v4, trace attributes (session_id, user_id, metadata, tags)
    are propagated to all observations via propagate_attributes().
    
    This function is a placeholder - you should use propagate_attributes()
    as a context manager in your code:
    
    Example:
        from langfuse import observe, propagate_attributes
        
        @observe()
        def my_func():
            with propagate_attributes(session_id="sess-123", user_id="user-456"):
                # Your code here
                pass
    
    Args:
        session_id: Session identifier
        user_id: User identifier
        **kwargs: Additional metadata (must be dict[str, str] in v4)
        
    Returns:
        False (this function is for documentation only)
    """
    return False


# Re-export commonly used items for convenience
__all__ = [
    "observe",
    "get_current_observation", 
    "get_current_trace",
    "get_client",
    "propagate_attributes",
    "flush_langfuse",
    "shutdown_langfuse",
    "update_current_observation_safe",
    "set_trace_attributes",
]
