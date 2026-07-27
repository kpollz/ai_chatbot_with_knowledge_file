# agent

The Machine Issue Solver agent, served over the AG-UI protocol.

## Endpoints

| Method | Path | |
| ------ | ---- | --- |
| `POST` | `/` | AG-UI |
| `GET` | `/health` | liveness |

CopilotKit connects with `LangGraphHttpAgent({ url })`.

## Layout

```
app/
├── main.py            AG-UI server: LangGraphAGUIAgent on FastAPI
├── agent.py           the compiled graph (create_react_agent)
├── graph.py           SYSTEM_PROMPT + the search_issues tool
├── llm.py             get_chat_model() — OpenAI-compatible endpoint
├── api_client.py      pooled HTTP client for the Issue API
├── config.py          environment configuration
├── langfuse_setup.py  optional tracing
└── logger.py          logging + Timer
```

Modules import each other by bare name; the Dockerfile copies `app/` into the
working directory.

## Behaviour

One tool, `search_issues(machine_name, line_name, location?, serial?)`, which
calls the Issue API over HTTP. Tool depth is bounded by
`recursion_limit = 2 * MAX_ITERATIONS + 1`.

The LLM endpoint must support client-side function calling. An endpoint that is
itself an agent with its own built-in tools ignores the `tools` parameter, and
`search_issues` never fires.

Conversation threads are checkpointed to the `agent_state` database, so they
survive restarts and are shared across replicas. Clients send only the new
message; history is restored from the checkpoint keyed by `threadId`.

```sql
SELECT thread_id, count(*) FROM checkpoints GROUP BY thread_id;
```

With both Langfuse keys set, every LLM call and tool step is traced as a nested
observation. Without them, tracing is a no-op.

The agent holds no user identity and no API keys — the platform in front of it
owns authentication and per-user keys.

## Run

```bash
docker compose up -d agent
```

Standalone, with the Issue API already running:

```bash
pip install -r requirements.txt
cp .env.example .env
cd app && uvicorn main:app --port 8123
```

## Environment

| Variable | | Default |
| -------- | --- | ------- |
| `ISSUE_API_URL` | Issue API base URL | `http://localhost:8888` |
| `OPENAI_BASE_URL` | OpenAI-compatible endpoint | — |
| `OPENAI_API_KEY` | key for that endpoint | — |
| `OPENAI_MODEL` | model name sent to it | — |
| `LLM_TEMPERATURE` | sampling temperature | `0` |
| `DATABASE_URI` | Postgres for the checkpointer | `postgresql://…/agent_state` |
| `LANGFUSE_PUBLIC_KEY` | optional — enables tracing | — |
| `LANGFUSE_SECRET_KEY` | optional — enables tracing | — |
| `LANGFUSE_HOST` | | `https://cloud.langfuse.com` |

See [docs/agui-integration.md](../docs/agui-integration.md) for why the agent is
served this way.
