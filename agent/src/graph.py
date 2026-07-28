"""The compiled graph.

Nothing supplies a checkpointer here — unlike the ``langgraph dev`` route, where
the server provides one — so ``main.py`` attaches a Postgres one at startup.

The model is a per-request function implementing BYOK (Bring Your Own Key):
it reads the API key from ``runtime.context`` (official AG-UI route) or from
the contextvar set by FastAPI middleware (fallback), then builds a ChatOpenAI
instance for that specific request.
"""

from langgraph.prebuilt import create_react_agent

from src import config
from src.context import AgentContext, get_request_api_key
from src.llm import get_chat_model
from src.prompts import SYSTEM_PROMPT
from src.tools import TOOLS

# Max tool-using steps before LangGraph stops. main.py turns this into the run's
# recursion_limit (2*N + 1: each step is a model call plus a tool call).
MAX_ITERATIONS = 3


def _dynamic_model(state: object, runtime: object) -> object:
    """Per-request model factory implementing BYOK.

    Reads the API key from:
    1. ``runtime.context[\"openai_api_key\"]`` — official AG-UI/LangGraph route.
    2. Contextvar ``_request_api_key`` — fallback set by FastAPI middleware.

    Falls back to the global ``OPENAI_API_KEY`` env var if neither is present.
    """
    key = None
    # Try runtime.context first (the official route)
    ctx = getattr(runtime, "context", None) or {}
    if isinstance(ctx, dict):
        key = ctx.get("openai_api_key")
    # Fallback to contextvar set by middleware
    key = key or get_request_api_key()
    # Final fallback to global env
    key = key or config.OPENAI_API_KEY or "not-needed"
    return get_chat_model(api_key=key)


graph = create_react_agent(
    model=_dynamic_model,
    tools=TOOLS,
    prompt=SYSTEM_PROMPT,
    context_schema=AgentContext,
)
