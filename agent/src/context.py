"""BYOK (Bring Your Own Key) — per-request API key context.

The FastAPI middleware reads ``x-openai-api-key`` from the request header and
stores it in a thread/task-local contextvar. The dynamic model function reads it
to build a per-request ``ChatOpenAI`` instance.

Two mechanisms are wired:
1. Contextvar ``_request_api_key`` — set by middleware, read by the model.
   LangGraph propagates contextvars into the run, same as the existing
   ``_issues_recorder`` side-channel.
2. ``runtime.context`` — official AG-UI/LangGraph route for per-request
   configurable values. Takes precedence when present.
"""

import contextvars
from typing import Optional

# pydantic >= 2.13 on Python < 3.12 rejects `typing.TypedDict` (it crashes
# langgraph's config_schema build with PydanticUserError). Use the
# typing_extensions form, which pydantic accepts on all versions.
from typing_extensions import TypedDict

_request_api_key: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "request_openai_api_key", default=None
)


def set_request_api_key(key: Optional[str]) -> None:
    """Store the per-request API key (called by middleware)."""
    _request_api_key.set(key)


def get_request_api_key() -> Optional[str]:
    """Retrieve the per-request API key (called by the dynamic model)."""
    return _request_api_key.get()


class AgentContext(TypedDict, total=False):
    """Schema for per-request configurable values passed via ``runtime.context``."""
    openai_api_key: str
