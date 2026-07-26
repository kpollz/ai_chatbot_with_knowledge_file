"""AG-UI agent-service.

Exposes the machine-issue-solver agent over the AG-UI protocol so any AG-UI
client (CopilotKit among them) can run it. The endpoint streams AG-UI events
over SSE; conversation state is keyed by the ``thread_id`` the client sends and
persisted by the checkpointer.

Run: ``uvicorn server:app --host 0.0.0.0 --port 8700``
"""

from contextlib import asynccontextmanager

from ag_ui_langgraph import LangGraphAgent, add_langgraph_fastapi_endpoint
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

# Reused from the chatbot sub-project (on PYTHONPATH):
from langfuse_setup import langchain_handler
from logger import logger

from agent_config import AGENT_API_KEY_HEADER
from agent_graph import AGENT_CONFIG, agent_graph
from checkpointer import close_checkpointer, open_checkpointer
from request_context import set_request_api_key

AGENT_NAME = "machine_issue_solver"
AGENT_DESCRIPTION = (
    "Trợ lý kỹ thuật tra cứu sự cố máy móc trong nhà máy: hiện tượng, "
    "nguyên nhân và cách khắc phục từ cơ sở dữ liệu issue."
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Built here rather than at import: the async Postgres saver binds to the
    # running event loop. Attaching it to the compiled graph is enough —
    # LangGraph reads .checkpointer on every run.
    agent_graph.checkpointer = await open_checkpointer()
    logger.info(f"Agent '{AGENT_NAME}' serving AG-UI on /")
    yield
    await close_checkpointer()


app = FastAPI(
    title="Machine Issue Solver — AG-UI agent",
    description="LangGraph ReAct agent exposed over the AG-UI protocol.",
    version="1.0.0",
    lifespan=lifespan,
)

# Browser-based AG-UI clients (CopilotKit) call this cross-origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def capture_api_key(request: Request, call_next):
    """Bind the caller's own LLM API key to this request (BYOK).

    The graph is shared by every user, so the key cannot be baked into it — it
    is stashed in a ContextVar here and read back when this run builds its model
    (see ``agent_graph._resolve_model``).
    """
    set_request_api_key(request.headers.get(AGENT_API_KEY_HEADER))
    return await call_next(request)


def _build_agent() -> LangGraphAgent:
    """Wrap the compiled graph as an AG-UI agent, with Langfuse tracing if on."""
    config = dict(AGENT_CONFIG)
    handler = langchain_handler()  # None when Langfuse is not configured
    if handler:
        config["callbacks"] = [handler]
        logger.info("Langfuse tracing enabled")
    return LangGraphAgent(
        name=AGENT_NAME,
        description=AGENT_DESCRIPTION,
        graph=agent_graph,
        config=config,
    )


add_langgraph_fastapi_endpoint(app=app, agent=_build_agent(), path="/")


@app.get("/health")
def health():
    """Liveness probe (the AG-UI endpoint registers its own under ``//health``)."""
    return {"status": "ok", "agent": AGENT_NAME}
