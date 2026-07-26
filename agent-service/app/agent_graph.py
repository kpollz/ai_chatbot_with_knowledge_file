"""The server-side ReAct agent graph.

Same agent as the Streamlit app — the prompt, the ``search_issues`` tool and the
LLM factory are imported from the chatbot sub-project rather than duplicated.
Two things differ, because this one is served over HTTP to many users:

1. The graph is compiled **once** at import and shared, instead of being rebuilt
   per call. So the model cannot be baked in — a callable resolves it per run
   from the caller's own API key (BYOK).
2. It carries a **checkpointer**, so conversation state lives in Postgres keyed
   by ``thread_id`` instead of being resent by the client every turn.

Named ``agent_graph`` so it cannot shadow the reused ``chatbot/app/graph.py``.
"""

from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.prebuilt import create_react_agent

# Reused from the chatbot sub-project (on PYTHONPATH):
from config import OPENAI_API_KEY
from graph import MAX_ITERATIONS, SYSTEM_PROMPT, TOOLS
from llm import get_chat_model
from logger import logger

from request_context import AgentContext, get_request_api_key


def _resolve_model(state, runtime) -> BaseChatModel:
    """Build this run's chat model from the caller's own API key.

    Called by LangGraph on every model step, inside the request's context, so
    each user's key stays scoped to their own run. Order of preference: the key
    passed as run context, then the request header, then the server's fallback
    key from the environment.
    """
    context_key = ""
    context = getattr(runtime, "context", None)
    if context is not None:
        context_key = (
            context.get("openai_api_key", "")
            if isinstance(context, dict)
            else getattr(context, "openai_api_key", "")
        )

    api_key = context_key or get_request_api_key() or OPENAI_API_KEY
    if not api_key:
        logger.warning("No LLM API key for this run — the model call will likely fail.")
    return get_chat_model(api_key=api_key)


# The checkpointer is attached in the server's lifespan, not here: the async
# Postgres saver binds to the running event loop, which does not exist at import
# time. LangGraph reads ``.checkpointer`` per run, so attaching it later works.
agent_graph = create_react_agent(
    model=_resolve_model,
    tools=TOOLS,
    prompt=SYSTEM_PROMPT,
    context_schema=AgentContext,
)

# Mirrors the Streamlit path: cap the ReAct loop at MAX_ITERATIONS tool steps.
AGENT_CONFIG = {"recursion_limit": 2 * MAX_ITERATIONS + 1}
