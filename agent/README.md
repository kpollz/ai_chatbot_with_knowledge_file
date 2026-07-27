# agent — Machine Issue Solver

One agent, one source tree, two ways to reach it:

| Entrypoint | Serves | Port |
| ---------- | ------ | ---- |
| `app/main.py` | the agent over the **AG-UI** protocol, for any AG-UI client | 8123 |
| `app/streamlit_app.py` | the Streamlit UI, until the CopilotKit front end replaces it | 8501 |

Both import the same `graph.py` — prompt, `search_issues` tool, LLM factory — so
there is one definition of the agent, not two. They previously lived in separate
directories with the server bind-mounting the other's source; that is gone.

## Layout

```
agent/
├── app/
│   ├── main.py               AG-UI server: LangGraphAGUIAgent on FastAPI
│   ├── agent.py              the compiled graph (create_react_agent)
│   ├── graph.py              SYSTEM_PROMPT, search_issues tool, solve_issue_stream
│   ├── llm.py                get_chat_model() — OpenAI-compatible endpoint
│   ├── api_client.py         pooled HTTP client for the Issue API
│   ├── config.py             environment configuration
│   ├── langfuse_setup.py     Langfuse v4 handler + trace attributes
│   ├── logger.py             logging + Timer
│   ├── streamlit_app.py      Streamlit chat page
│   ├── history.py            token estimation, context-window guards
│   ├── conversation_store.py JSON session storage
│   ├── feedback.py           star-rating widget → Langfuse scores
│   └── pages/1_Issues.py     issue CRUD page
├── Dockerfile                one image; compose picks the entrypoint
└── requirements.txt
```

Modules import each other by bare name and the Dockerfile copies `app/` into the
working directory, so no path setup is needed either way.

## The agent

`create_react_agent` over an OpenAI-compatible endpoint with native tool calling.
One tool:

| Tool | |
| ---- | --- |
| `search_issues(machine_name, line_name, location?, serial?)` | issues for a machine on a line |

It calls the **Issue API** over HTTP — no direct database access.

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
that attribute on every run.

The agent holds no user identity and no API keys. Authentication, accounts and
per-user keys belong to the platform in front of it.

## Run

Under Docker Compose both services come up together:

```bash
docker compose up -d agent chatbot
```

Standalone, with the Issue API already running:

```bash
pip install -r requirements.txt
cp .env.example .env          # then fill it in

cd app
uvicorn main:app --port 8123  # AG-UI
streamlit run streamlit_app.py
```

### Environment

| Variable | | Default |
| -------- | --- | ------- |
| `ISSUE_API_URL` | Issue API base URL | `http://localhost:8888` |
| `OPENAI_BASE_URL` | OpenAI-compatible endpoint | — |
| `OPENAI_API_KEY` | key for that endpoint | — |
| `OPENAI_MODEL` | model name sent to it | — |
| `LLM_TEMPERATURE` | sampling temperature | `0` |
| `DATABASE_URI` | Postgres for the checkpointer (AG-UI only) | `postgresql://postgres:postgres@localhost:5432/agent_state` |
| `CONTEXT_WINDOW_LIMIT` | tokens before input is blocked (Streamlit only) | `128000` |
| `CONTEXT_WARN_THRESHOLD` | tokens before a warning (Streamlit only) | `100000` |
| `LANGFUSE_PUBLIC_KEY` | optional | — |
| `LANGFUSE_SECRET_KEY` | optional | — |
| `LANGFUSE_HOST` | | `https://cloud.langfuse.com` |

## Streamlit specifics

- streaming responses with step-by-step status updates
- conversation history within a session; token estimation with warn/block thresholds
- star feedback per answer, scored into Langfuse
- issue CRUD page
- sessions auto-saved to `conversations/` as JSON
