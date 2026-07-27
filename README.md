# Machine Issue Solver

A LangGraph agent that answers questions about factory machine issues — symptom,
cause, fix — from a recorded issue database. It is served over the **AG-UI**
protocol, so any AG-UI client drives it by URL.

```
   AG-UI client (CopilotKit, …)
            │  AG-UI over HTTP+SSE
            ▼
   ┌────────────────────────┐
   │  agent           :8123 │
   └───┬────────────────┬───┘
       │                │  search_issues (HTTP)
       │                ▼
       │    ┌───────────────────────────┐
       │    │ Issue API (FastAPI) :8888 │
       │    └─────────────┬─────────────┘
       │ threads          │
       ▼                  ▼
   ┌─────────────────────────────────────────────────┐
   │ PostgreSQL 16                                   │
   │   agent_state  — conversation checkpoints       │
   │   issue_api    — teams, lines, machines, issues │
   └─────────────────────────────────────────────────┘
```

- **[agent/](agent/)** — the agent and its AG-UI endpoint (8123)
- **[issue-api/](issue-api/)** — the only service that touches the database (8888)
- **PostgreSQL 16** — `issue_api` and `agent_state`

The front end is a separate project; this repo ships the agent.

## Quick start

```bash
cp .env.example .env      # fill in OPENAI_BASE_URL, OPENAI_API_KEY, OPENAI_MODEL
docker compose up -d
```

Every service reads that one `.env`.

| | |
| --- | --- |
| AG-UI endpoint | `POST http://localhost:8123/` — health at `/health` |
| Issue API docs | http://localhost:8888/docs |

Locally instead of Docker:

```bash
pip install -r agent/requirements.txt -r issue-api/requirements.txt openpyxl
docker compose up -d postgres
cd issue-api/app && python main.py           # terminal 2
cd agent && uvicorn main:app --port 8123      # terminal 3
```

## Structure

```
machine-issue-solver/
├── agent/            the agent, served over AG-UI       → agent/README.md
├── issue-api/        FastAPI service owning the data    → issue-api/README.md
├── docs/             design notes and decisions
├── postgres-init/    creates the agent_state database on first init
├── import_excel.py   bulk-import factory data from Excel
├── fake_excel.py     generate test data for the importer
├── streaming_sample.py  standalone SSE demo against a raw LLM endpoint
└── docker-compose.yml
```

## Stack

LangGraph (`create_react_agent`) · AG-UI via `ag-ui-langgraph` + `copilotkit` ·
FastAPI · PostgreSQL 16 with `AsyncPostgresSaver` for threads · SQLAlchemy 2.0
async · any OpenAI-compatible LLM endpoint with function calling · Langfuse v4
tracing, optional.

## Docs

- [AG-UI integration](docs/agui-integration.md) — how the agent is served, and why this way
