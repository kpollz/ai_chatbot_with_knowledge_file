# Machine Issue Solver

A LangGraph agent that diagnoses factory machine issues, served over the **AG-UI**
protocol so any AG-UI client can drive it by URL. Issue data lives behind a
FastAPI service.

## Architecture

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

One `create_react_agent` over an OpenAI-compatible endpoint with native tool
calling. Conversation threads live in Postgres, so they survive restarts and are
shared across replicas.

Three services from the repo root:

- **[Agent](agent/)** — the AG-UI endpoint (8123)
- **[Issue API](issue-api/)** — FastAPI service owning all database access (8888)
- **PostgreSQL 16** — two databases: `issue_api` and `agent_state`

There is no front end in this repo. The Streamlit UI it used to ship was replaced
by the AG-UI endpoint; a CopilotKit front end is the next step, and must talk to
the agent through `LangGraphHttpAgent({url})` — not `LangGraphAgent`, which
targets the LangGraph Platform's different protocol.

## Quick Start

### 1. Configure

```bash
cp agent/.env.example agent/.env
# Edit agent/.env → OPENAI_BASE_URL, OPENAI_API_KEY, OPENAI_MODEL

cp issue-api/.env.example issue-api/.env
# Edit issue-api/.env → DATABASE_URL if needed
```

### 2. Run with Docker (recommended)

```bash
docker compose up -d          # postgres + issue-api + agent
docker compose logs -f
docker compose down
```

Both databases are created on first start — `agent_state` by
`postgres-init/01-create-agent-db.sh`.

### 3. Run locally for development

```bash
python -m venv venv && source venv/bin/activate
pip install -r agent/requirements.txt -r issue-api/requirements.txt openpyxl

# Terminal 1 — PostgreSQL
docker compose up -d postgres

# Terminal 2 — Issue API
cd issue-api/app && python main.py

# Terminal 3 — the agent
cd agent/app && uvicorn main:app --port 8123
```

Access points:

| | |
| --- | --- |
| AG-UI endpoint | `POST http://localhost:8123/` (health at `/health`) |
| Issue API docs | http://localhost:8888/docs |

## Features

| Feature | Description |
|---------|-------------|
| **AG-UI endpoint** | Any AG-UI client drives the agent by URL; CopilotKit via `LangGraphHttpAgent` |
| **Persistent threads** | Postgres checkpointer — conversations survive restarts and are shared across replicas |
| **ReAct agent** | Native function calling; the LLM calls `search_issues` when it needs data |
| **Streaming** | Token-by-token AG-UI events (`TEXT_MESSAGE_*`, `STATE_SNAPSHOT`, …) |
| **Langfuse tracing** | Optional; every LLM call and tool step as nested observations |
| **Issue CRUD** | REST endpoints on the Issue API (Swagger at :8888/docs) |
| **Excel import** | `import_excel.py`, auto-creating teams/lines/machines |

## Project Structure

```
machine-issue-solver/
├── agent/                      # Sub-project 1: the agent, served over AG-UI
│   ├── app/
│   │   ├── main.py             # AG-UI server (FastAPI, port 8123)
│   │   ├── agent.py            # compiled graph (create_react_agent)
│   │   ├── graph.py            # SYSTEM_PROMPT + the search_issues tool
│   │   ├── llm.py              # get_chat_model() — OpenAI-compatible endpoint
│   │   ├── api_client.py       # Pooled HTTP client for Issue API
│   │   ├── config.py           # Configuration
│   │   ├── langfuse_setup.py   # Optional tracing
│   │   └── logger.py           # Logging + Timer
│   ├── .env.example
│   ├── requirements.txt
│   ├── Dockerfile
│   └── README.md
│
├── issue-api/                  # Sub-project 2: FastAPI Issue Service
│   ├── app/
│   │   ├── main.py             # FastAPI entry point
│   │   ├── config.py           # Configuration
│   │   ├── database.py         # Async SQLAlchemy engine
│   │   ├── models.py           # ORM models: Team, Line, Machine, Issue
│   │   ├── schemas.py          # Pydantic schemas
│   │   ├── crud.py             # CRUD operations
│   │   └── routes.py           # REST endpoints
│   ├── postgres_data/          # PostgreSQL Docker volume
│   ├── .env.example
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── docker-compose.yml      # PostgreSQL + API only
│   ├── MIGRATION.md            # SQLite → PostgreSQL migration notes
│   └── README.md
│
├── postgres-init/              # Runs once on first DB init
│   └── 01-create-agent-db.sh   # creates the agent_state database
├── import_excel.py             # Standalone Excel data importer
├── fake_excel.py               # Generate fake test data
├── streaming_sample.py         # Standalone SSE demo against a raw endpoint
├── docker-compose.yml          # Full-stack compose
├── .gitignore
└── README.md                   # This file
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| LLM | Any OpenAI-compatible endpoint with function calling |
| Agent framework | LangGraph (`create_react_agent`) + LangChain |
| Agent protocol | AG-UI via `ag-ui-langgraph` + `copilotkit` |
| Thread persistence | `AsyncPostgresSaver` (langgraph-checkpoint-postgres) |
| API | FastAPI + Uvicorn |
| Database | PostgreSQL 16 + SQLAlchemy 2.0 (async) + asyncpg |
| HTTP client | httpx (pooled) |
| Tracing | Langfuse v4 (optional) |
| Excel processing | openpyxl (standalone importer) |
| Containerization | Docker + Docker Compose |
