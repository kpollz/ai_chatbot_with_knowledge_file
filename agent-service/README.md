# agent-service — the Machine Issue Solver, spoken over AG-UI

A plain FastAPI process that mounts the LangGraph agent behind the AG-UI
protocol. Any AG-UI client can drive it by URL alone, which is the whole point:
the platform registers an agent by pasting an address, nothing more.

This follows CopilotKit's official
[`langgraph-fastapi`](https://github.com/CopilotKit/CopilotKit/tree/main/examples/integrations/langgraph-fastapi)
example rather than the `langgraph-python` one. Both exist upstream and differ
in exactly one thing — how the Python agent is run:

|                     | `langgraph-python`                          | `langgraph-fastapi` (this)             |
| ------------------- | ------------------------------------------- | -------------------------------------- |
| Run                 | `langgraph dev` (CLI, needs Docker)         | `uvicorn main:app`                     |
| Server code         | none                                        | this file, ~40 lines                   |
| Protocol to the FE  | LangGraph Platform REST                     | AG-UI directly                         |
| CopilotKit client   | `LangGraphAgent({deploymentUrl, graphId})`  | `LangGraphHttpAgent({url})`            |
| Checkpointer        | supplied by the server                      | ours to choose                         |

Upstream's own Dockerfile makes the case for this variant: it deletes the
`LangGraphAgent` route, swaps in an HTTP one and drops `langgraph-cli` entirely,
because that CLI needs Docker-in-Docker. Running the licensed LangGraph Server
instead fails at boot with `License verification failed`. A FastAPI process has
neither problem.

## Layout

```
main.py         FastAPI app: LangGraphAGUIAgent + add_langgraph_fastapi_endpoint
src/agent.py    the graph — create_react_agent over the shared prompt and tools
```

The prompt, the `search_issues` tool and the LLM factory are imported from
`chatbot/app/` (bind-mounted at `/chatbot/app`) so there is one definition of
the agent, not two.

## Threads

Where the upstream example uses `MemorySaver` — a dictionary in RAM, gone on
restart and invisible to other replicas — this service attaches an
`AsyncPostgresSaver`. Threads land in the `agent_state` database, survive
restarts and are queryable:

```sql
SELECT thread_id, count(*) FROM checkpoints GROUP BY thread_id;
```

The saver binds to the running event loop in its constructor, so it is built in
the FastAPI lifespan and assigned to `graph.checkpointer` there; LangGraph reads
that attribute on every run.

## Endpoints

| Method | Path      | |
| ------ | --------- | --- |
| `POST` | `/`       | the AG-UI endpoint |
| `GET`  | `/health` | liveness |

## Scope

The agent holds no user identity and no API keys. Authentication, accounts and
per-user keys belong to the platform in front of it.
