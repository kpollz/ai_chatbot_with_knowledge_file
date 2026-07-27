# AG-UI integration

Why the agent is served the way it is. For how to run it, see
[agent/README.md](../agent/README.md).

## Choice of integration

CopilotKit publishes two LangGraph integrations. They are the same project apart
from how the Python agent runs:

|                    | `langgraph-python`                         | `langgraph-fastapi` (used here) |
| ------------------ | ------------------------------------------ | ------------------------------- |
| Run                | `langgraph dev` (CLI, needs Docker)        | `uvicorn main:app`              |
| Server code        | none                                       | ~40 lines                       |
| Protocol to the FE | LangGraph Platform REST                    | AG-UI directly                  |
| CopilotKit client  | `LangGraphAgent({deploymentUrl, graphId})` | `LangGraphHttpAgent({url})`     |
| Checkpointer       | supplied by the server                     | ours to choose                  |

Two things decided it:

- Upstream's own Dockerfile converges on the FastAPI shape. In both examples it
  deletes the `LangGraphAgent` route, substitutes an HTTP one and drops
  `langgraph-cli` entirely — that CLI needs Docker-in-Docker, which many
  platforms do not provide.
- The licensed LangGraph Server refuses to boot without a licence key
  (`ValueError: License verification failed`). Self-hosted LangSmith is
  enterprise-only and is observability anyway, so it does not unlock the server.

A plain FastAPI process has neither constraint.

## Threads

The upstream example uses `MemorySaver`, which is `InMemorySaver` — a nested
`defaultdict`. Threads die with the process and are invisible to other replicas.
This agent uses `AsyncPostgresSaver` against its own `agent_state` database
instead.

Three constraints shaped the wiring:

- It must be the **async** saver: `ag-ui-langgraph` drives `astream_events` and
  `aget_state`.
- `AsyncPostgresSaver.__init__` calls `asyncio.get_running_loop()`, so it cannot
  be constructed at import time. The graph is compiled without a checkpointer and
  `graph.checkpointer` is assigned in the FastAPI lifespan; LangGraph reads that
  attribute on every run.
- `from_conn_string` is a context manager, unsuitable for a long-lived server —
  hence an `AsyncConnectionPool` with
  `{autocommit: True, prepare_threshold: 0, row_factory: dict_row}`.

The checkpointer owns the schema of whatever database it is given, so it does not
share one with the Issue API. `postgres-init/01-create-agent-db.sh` creates
`agent_state` on first initialisation of the data volume.

## Per-run config

`LangGraphAGUIAgent(config=…)` takes a `RunnableConfig` that ag-ui copies into
every run before injecting `configurable.thread_id`. Both the recursion limit and
the Langfuse callback handler are attached there.

## Scope

Authentication, user accounts and per-user API keys belong to the platform in
front of the agent. The agent holds no identity and no keys, which is what lets
it be registered as nothing but a URL.

## Known gaps

- **Langfuse traces are not grouped per conversation.** `LangGraphAGUIAgent`
  takes one static config, while Langfuse reads `session_id` from per-run
  metadata. Traces are complete but not keyed to `threadId`.
- **Tool calling depends on the endpoint.** A model endpoint that is itself an
  agent with built-in tools ignores the client-supplied `tools`, so
  `search_issues` never fires. Needs a plain function-calling model.
