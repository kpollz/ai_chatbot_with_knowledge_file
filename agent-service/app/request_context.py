"""Per-request BYOK key plumbing.

Every user brings their own LLM API key, so the key cannot live on the compiled
graph — the graph is built once at startup and shared by all requests. Instead
the key travels in a ``ContextVar``: middleware sets it from the request header,
and the graph's dynamic-model function reads it when that request's run builds
its ChatOpenAI client.

A ContextVar is the right tool because each request runs in its own asyncio task
and inherits its own copy of the context — concurrent users cannot see each
other's key. Verified to survive into the StreamingResponse generator (which is
where the AG-UI endpoint actually runs the graph). This is the same mechanism
``chatbot/app/graph.py`` already uses for its issues recorder.
"""

import contextvars
from typing import Optional

from pydantic import BaseModel

_request_api_key: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "request_llm_api_key", default=None
)


def set_request_api_key(key: Optional[str]) -> None:
    """Store the caller's LLM API key for the duration of this request."""
    _request_api_key.set(key or None)


def get_request_api_key() -> Optional[str]:
    """The current request's LLM API key, or None when the caller sent none."""
    return _request_api_key.get()


class AgentContext(BaseModel):
    """Runtime context schema for the graph.

    Declared so AG-UI/LangGraph can advertise and pass per-run values. The key
    normally arrives via the request header (see ``set_request_api_key``); this
    field lets a caller pass it as run context instead. Pydantic (not a
    dataclass) because ag-ui-langgraph introspects it with ``.schema()``.
    """

    openai_api_key: str = ""
