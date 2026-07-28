# agent

The Machine Issue Solver agent, served over the AG-UI protocol.

## Endpoints

| Method | Path | |
| ------ | ---- | --- |
| `POST` | `/agent` | AG-UI |
| `GET` | `/agent/health` | AG-UI health |
| `GET` | `/health` | liveness |

CopilotKit connects with ``LangGraphHttpAgent({ url: "http://…:8123/agent" })``.

## Layout

```
main.py               AG-UI server: LangGraphAGUIAgent on FastAPI
src/
├── graph.py          the compiled graph (create_react_agent)
├── prompts.py        SYSTEM_PROMPT
├── tools.py          search_issues + TOOLS
├── llm.py            get_chat_model() — OpenAI-compatible endpoint
├── api_client.py     pooled HTTP client for the Issue API
├── config.py         environment configuration
├── langfuse_setup.py optional tracing
└── logger.py         logging + Timer
```

One module per role, which is how LangGraph's own project templates and
CopilotKit's Python examples both lay an agent out. Sub-folders start earning
their keep when a role outgrows one file — `tools/` once there are several tools.

## Behaviour

One tool, `search_issues(machine_name, line_name, location?, serial?)`, which
calls the Issue API over HTTP. Tool depth is bounded by
`recursion_limit = 2 * MAX_ITERATIONS + 1`.

The LLM endpoint must support client-side function calling. An endpoint that is
itself an agent with its own built-in tools ignores the `tools` parameter, and
`search_issues` never fires.

### BYOK (Bring Your Own Key)

Callers may supply a per-request API key via the `x-openai-api-key` header.
The model for that request is built with the supplied key; requests without the
header fall back to the global `OPENAI_API_KEY` env var.

```bash
# With BYOK
curl -X POST http://localhost:8123/agent \
  -H "x-openai-api-key: sk-user-123" \
  -H "Content-Type: application/json" \
  -d '{"message": {"role": "user", "content": "…"}, "configurable": {"thread_id": "…"}}'
```

Two routes to the model:
1. **Header `x-openai-api-key`** → FastAPI middleware → contextvar → dynamic model
2. **`configurable.openai_api_key`** in the run payload → official AG-UI route

The platform owning the agent can implement per-user keys by injecting the header
or adding the configurable field on the proxy path.

### Conversation state

Conversation threads are checkpointed to the `agent_state` database, so they
survive restarts and are shared across replicas. Clients send only the new
message; history is restored from the checkpoint keyed by `threadId`.

```sql
SELECT thread_id, count(*) FROM checkpoints GROUP BY thread_id;
```

With both Langfuse keys set, every LLM call and tool step is traced as a nested
observation. Without them, tracing is a no-op.

## Run

```bash
docker compose up -d agent
```

Standalone, with the Issue API already running:

```bash
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --port 8123
```

## Environment

| Variable | | Default |
| -------- | --- | ------- |
| `ISSUE_API_URL` | Issue API base URL | `http://localhost:8888` |
| `OPENAI_BASE_URL` | OpenAI-compatible endpoint | — |
| `OPENAI_API_KEY` | **fallback** key for that endpoint | — |
| `OPENAI_MODEL` | model name sent to it | — |
| `LLM_TEMPERATURE` | sampling temperature | `0` |
| `DATABASE_URI` | Postgres for the checkpointer | `postgresql://…/agent_state` |
| `LANGFUSE_PUBLIC_KEY` | optional — enables tracing | — |
| `LANGFUSE_SECRET_KEY` | optional — enables tracing | — |
| `LANGFUSE_HOST` | | `https://cloud.langfuse.com` |

**Per-request keys** are sent via the `x-openai-api-key` header or
`configurable.openai_api_key` in the AG-UI run payload. The env var above is the
fallback when neither is present.

See [docs/agui-integration.md](../docs/agui-integration.md) for why the agent is
served this way.
