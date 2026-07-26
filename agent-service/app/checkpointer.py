"""LangGraph checkpointer — durable multi-turn conversation state.

This is what makes the agent usable from a stateless frontend: the client sends
a ``thread_id`` with each run, and LangGraph reloads that thread's messages from
Postgres. It survives restarts, unlike the in-memory savers.

We use the **async** saver on a connection pool because ag-ui-langgraph drives
the graph asynchronously (``astream_events`` / ``aget_state``).

``AsyncPostgresSaver`` binds to the running event loop in its constructor, so it
cannot be built at import time. It is created during the server's lifespan and
attached to the already-compiled graph then — LangGraph reads ``.checkpointer``
per run, so attaching it after compilation persists state normally.

The checkpointer keeps its own tables (``checkpoints``, ``checkpoint_blobs``,
``checkpoint_writes``); they do not collide with the Issue API's tables, which
is why sharing the same database is safe.
"""

from typing import Optional

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from agent_config import CHECKPOINT_DATABASE_URL
from logger import logger  # reused from the chatbot sub-project

_pool: Optional[AsyncConnectionPool] = None
checkpointer: Optional[AsyncPostgresSaver] = None


async def open_checkpointer() -> AsyncPostgresSaver:
    """Open the pool, ensure the checkpoint tables exist, return the saver."""
    global _pool, checkpointer

    # Connection settings mirror what AsyncPostgresSaver.from_conn_string()
    # applies; a pool is used instead so concurrent requests share connections.
    _pool = AsyncConnectionPool(
        conninfo=CHECKPOINT_DATABASE_URL,
        min_size=1,
        max_size=10,
        open=False,
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
    )
    await _pool.open(wait=True)

    checkpointer = AsyncPostgresSaver(_pool)
    await checkpointer.setup()  # idempotent
    logger.info("Checkpointer ready (Postgres tables ensured)")
    return checkpointer


async def close_checkpointer() -> None:
    """Release the connection pool on shutdown."""
    if _pool is not None:
        await _pool.close()
        logger.info("Checkpointer pool closed")
