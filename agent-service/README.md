# Agent Service (AG-UI)

Serves the machine-issue-solver LangGraph agent over the **AG-UI protocol**, so
any AG-UI client — CopilotKit among them — can run it. This is the pilot of the
"one agent-service per project" pattern; the Streamlit app in `../chatbot` keeps
working unchanged and is untouched by this service.

```
AG-UI client ──HTTP/SSE──► agent-service :8700 ──► Issue API :8888 ──► Postgres
                                  │
                                  └── checkpoints (Postgres, same DB)
```

## What is different from the Streamlit path

| | `chatbot/` (Streamlit) | `agent-service/` (this) |
|---|---|---|
| Graph | rebuilt per call | compiled once, shared |
| Model | baked in at build time | resolved per run from the caller's key |
| Memory | client resends history | checkpointer, keyed by `thread_id` |
| Output | Streamlit events | AG-UI events over SSE |

The prompt, the `search_issues` tool, the LLM factory and the Langfuse setup are
**imported** from `../chatbot/app` (mounted at `/chatbot_app`, on `PYTHONPATH`),
not copied — there is one definition of the agent's behaviour.

## Run

```bash
docker compose up -d agent          # from the repo root
curl localhost:8700/health          # {"status":"ok","agent":"machine_issue_solver"}
```

Config: copy `.env.example` to `.env` (or set the vars in `docker-compose.yml`).

## Calling it

`POST /` with a `RunAgentInput` body and an SSE `accept` header. Each user sends
**their own** LLM API key in the `x-openai-api-key` header (BYOK) — the server's
`OPENAI_API_KEY` is only a fallback.

```jsonc
{
  "threadId": "<uuid>",     // same id on later turns = same conversation
  "runId": "<uuid>",
  "state": {}, "messages": [{"id": "<uuid>", "role": "user", "content": "..."}],
  "tools": [], "context": [], "forwardedProps": {}
}
```

Send only the *new* message on later turns — the checkpointer supplies the rest.

## Files

| File | Purpose |
|---|---|
| `app/server.py` | FastAPI app, AG-UI endpoint, BYOK middleware, lifespan |
| `app/agent_graph.py` | Compiled ReAct graph + per-run model resolution |
| `app/checkpointer.py` | Async Postgres checkpointer (opened in the lifespan) |
| `app/request_context.py` | Per-request API key (ContextVar) + context schema |
| `app/agent_config.py` | Server-only settings (checkpoint DB, port, key header) |

Module names are prefixed (`agent_graph`, `agent_config`) so they cannot shadow
the reused `chatbot/app/graph.py` and `config.py` on `PYTHONPATH`.

## Notes

- **Checkpoint tables** (`checkpoints`, `checkpoint_blobs`, `checkpoint_writes`)
  live in the same database as the Issue API; the names do not collide.
  `CHECKPOINT_DATABASE_URL` uses the sync `postgresql://` driver, unlike the
  Issue API's `postgresql+asyncpg://`.
- **Tool calling depends on the model.** `hermes-agent` is a self-contained agent
  that ignores client-supplied tools, so `search_issues` will not fire under it.
  Point `OPENAI_MODEL` at a plain function-calling model to exercise the tool.
