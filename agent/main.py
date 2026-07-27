"""Serve the agent over the AG-UI protocol.

The graph lives in ``src/``; this file wraps it in
``LangGraphAGUIAgent`` and mounts it on FastAPI with
``add_langgraph_fastapi_endpoint``, so any AG-UI client can drive it by URL.

``AsyncPostgresSaver`` binds to the running event loop in ``__init__``, so the
checkpointer is built in the lifespan and assigned to ``graph.checkpointer``
there — LangGraph reads that attribute on every run.

See ``docs/agui-integration.md`` for the reasoning behind this setup.
"""

import os
from contextlib import asynccontextmanager

import uvicorn
from ag_ui_langgraph import add_langgraph_fastapi_endpoint
from copilotkit import LangGraphAGUIAgent
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from src.config import DATABASE_URI
from src.graph import MAX_ITERATIONS, graph
from src.langfuse_setup import langchain_handler
from src.logger import logger

# The identifier an AG-UI client registers the agent under.
AGENT_NAME = "machine_issue_solver"

# Opened in the lifespan, for the event-loop reason given above.
_pool = AsyncConnectionPool(
    conninfo=DATABASE_URI,
    min_size=1,
    max_size=10,
    open=False,
    kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
)


def _run_config() -> dict:
    """The RunnableConfig ag-ui copies into every run.

    It adds ``configurable.thread_id`` per request; everything else is set once
    here. Each step is a model call plus a tool call, hence 2*N + 1.
    """
    config: dict = {"recursion_limit": 2 * MAX_ITERATIONS + 1}

    handler = langchain_handler()  # None when Langfuse is not configured
    if handler:
        config["callbacks"] = [handler]
        logger.info("Langfuse tracing enabled")
    return config


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _pool.open(wait=True)
    checkpointer = AsyncPostgresSaver(_pool)
    await checkpointer.setup()  # creates the checkpoint tables once
    graph.checkpointer = checkpointer
    yield
    await _pool.close()


app = FastAPI(title="Machine Issue Solver — AG-UI agent", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok", "agent": AGENT_NAME}


add_langgraph_fastapi_endpoint(
    app=app,
    agent=LangGraphAGUIAgent(
        name=AGENT_NAME,
        description="Tra cứu sự cố máy móc nhà máy: hiện tượng, nguyên nhân, cách khắc phục.",
        graph=graph,
        config=_run_config(),
    ),
    path="/",
)


def main():
    """Run the uvicorn server."""
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8123")))


if __name__ == "__main__":
    main()
