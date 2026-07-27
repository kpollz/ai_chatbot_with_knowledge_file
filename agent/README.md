# agent — Machine Issue Solver

A LangGraph agent served over the **AG-UI** protocol. Any AG-UI client can drive
it by URL alone, which is the whole point: the platform registers an agent by
pasting an address, nothing more.

There is no UI here. The Streamlit app that used to live in this tree was
replaced by the AG-UI endpoint; the front end is a separate concern.

## Layout

```
agent/
├── app/
│   ├── main.py            AG-UI server: LangGraphAGUIAgent on FastAPI
│   ├── agent.py           the compiled graph (create_react_agent)
│   ├── graph.py           SYSTEM_PROMPT + the search_issues tool
│   ├── llm.py             get_chat_model() — OpenAI-compatible endpoint
│   ├── api_client.py      pooled HTTP client for the Issue API
│   ├── config.py          environment configuration
│   ├── langfuse_setup.py  optional tracing
│   └── logger.py          logging + Timer
├── Dockerfile
└── requirements.txt
```

Modules import each other by bare name and the Dockerfile copies `app/` into the
working directory, so no path setup is needed.

## The agent

`create_react_agent` over an OpenAI-compatible endpoint with native tool calling.
One tool:

| Tool | |
| ---- | --- |
| `search_issues(machine_name, line_name, location?, serial?)` | issues for a machine on a line |

It calls the **Issue API** over HTTP — no direct database access. Tool depth is
bounded by `recursion_limit = 2 * MAX_ITERATIONS + 1`.

The model must support client-side function calling. An endpoint that is itself
an agent with its own built-in tools will ignore the `tools` parameter, and
`search_issues` will never fire.

## AG-UI

`app/main.py` follows CopilotKit's official
[`langgraph-fastapi`](https://github.com/CopilotKit/CopilotKit/tree/main/examples/integrations/langgraph-fastapi)
example. Upstream ships two LangGraph integrations differing in one thing — how
the Python agent runs:

|                    | `langgraph-python`                         | `langgraph-fastapi` (this)  |
| ------------------ | ------------------------------------------ | --------------------------- |
| Run                | `langgraph dev` (CLI, needs Docker)        | `uvicorn main:app`          |
| Server code        | none                                       | ~40 lines                   |
| Protocol to the FE | LangGraph Platform REST                    | AG-UI directly              |
| CopilotKit client  | `LangGraphAgent({deploymentUrl, graphId})` | `LangGraphHttpAgent({url})` |
| Checkpointer       | supplied by the server                     | ours to choose              |

Upstream's own Dockerfile argues for this variant: it deletes the
`LangGraphAgent` route, swaps in an HTTP one and drops `langgraph-cli` entirely,
because that CLI needs Docker-in-Docker. The licensed LangGraph Server is worse
still — it fails at boot with `License verification failed`. A FastAPI process
has neither problem.

| Method | Path      | |
| ------ | --------- | --- |
| `POST` | `/`       | the AG-UI endpoint |
| `GET`  | `/health` | liveness |

### Threads

Where upstream uses `MemorySaver` — a dictionary in RAM, gone on restart and
invisible to other replicas — this attaches an `AsyncPostgresSaver`. Threads land
in the `agent_state` database, survive restarts and are queryable:

```sql
SELECT thread_id, count(*) FROM checkpoints GROUP BY thread_id;
```

The saver binds to the running event loop in its constructor, so it is built in
the FastAPI lifespan and assigned to `graph.checkpointer` there; LangGraph reads
that attribute on every run. Clients send only the new message — history is
restored from the checkpoint keyed by `threadId`.

### Tracing

With `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` set, a
`langfuse.langchain.CallbackHandler` is attached to the config the AG-UI agent
copies into every run, so each LLM call and tool step appears as a nested
observation. Without keys, tracing is a no-op.

Traces are not yet grouped per conversation: `LangGraphAGUIAgent` takes one
static config, and Langfuse reads `session_id` from per-run metadata that a
static config cannot carry.

### Scope

The agent holds no user identity and no API keys. Authentication, accounts and
per-user keys belong to the platform in front of it.

## Run

```bash
docker compose up -d agent
```

Standalone, with the Issue API already running:

```bash
pip install -r requirements.txt
cp .env.example .env          # then fill it in
cd app && uvicorn main:app --port 8123
```

### Environment

| Variable | | Default |
| -------- | --- | ------- |
| `ISSUE_API_URL` | Issue API base URL | `http://localhost:8888` |
| `OPENAI_BASE_URL` | OpenAI-compatible endpoint | — |
| `OPENAI_API_KEY` | key for that endpoint | — |
| `OPENAI_MODEL` | model name sent to it | — |
| `LLM_TEMPERATURE` | sampling temperature | `0` |
| `DATABASE_URI` | Postgres for the checkpointer | `postgresql://postgres:postgres@localhost:5432/agent_state` |
| `LANGFUSE_PUBLIC_KEY` | optional — enables tracing | — |
| `LANGFUSE_SECRET_KEY` | optional — enables tracing | — |
| `LANGFUSE_HOST` | | `https://cloud.langfuse.com` |
