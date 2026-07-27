# Machine Issue Solver

A LangGraph agent that diagnoses factory machine issues, reachable two ways: over
the **AG-UI** protocol by any AG-UI client, and through a Streamlit UI. Issue data
lives behind a FastAPI service.

## Architecture

```
   AG-UI client (CopilotKit, …)              Streamlit UI
            │  AG-UI over HTTP+SSE                │  localhost:8501
            ▼                                     ▼
   ┌──────────────────────┐            ┌──────────────────────┐
   │  app/main.py  :8123  │            │  app/streamlit_app   │
   └──────────┬───────────┘            └──────────┬───────────┘
              └────────── same graph.py ──────────┘
                     │                        │
       threads       │                        │  search_issues (HTTP)
                     │                        ▼
                     │            ┌───────────────────────────┐
                     │            │ Issue API (FastAPI) :8888 │
                     │            └─────────────┬─────────────┘
                     ▼                          ▼
       ┌─────────────────────────────────────────────────────┐
       │ PostgreSQL 16                                       │
       │   agent_state  — conversation checkpoints           │
       │   issue_api    — teams, lines, machines, issues     │
       └─────────────────────────────────────────────────────┘
```

Both entrypoints run the same agent — one `create_react_agent` over an
OpenAI-compatible endpoint with native tool calling. Only the AG-UI entrypoint
keeps threads in Postgres; the Streamlit one holds history in its session.

Four services from the repo root:

- **[Agent](agent/)** — the AG-UI endpoint (8123) and the Streamlit UI (8501), one image
- **[Issue API](issue-api/)** — FastAPI service owning all database access (8888)
- **PostgreSQL 16** — two databases: `issue_api` and `agent_state`

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
docker compose up -d          # postgres + issue-api + agent + chatbot
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

# Terminal 3 — pick an entrypoint
cd agent/app && uvicorn main:app --port 8123        # AG-UI
cd agent/app && streamlit run streamlit_app.py      # Streamlit
```

Access points:

| | |
| --- | --- |
| AG-UI endpoint | `POST http://localhost:8123/` (health at `/health`) |
| Streamlit UI | http://localhost:8501 |
| Issue API docs | http://localhost:8888/docs |

## Features

| Feature | Description |
|---------|-------------|
| **AG-UI endpoint** | Any AG-UI client drives the agent by URL; CopilotKit via `LangGraphHttpAgent` |
| **Persistent threads** | Postgres checkpointer — conversations survive restarts and are shared across replicas |
| **ReAct agent** | Native function calling; the LLM calls `search_issues` when it needs data |
| **Streaming** | Token-by-token output with step-by-step status updates |
| **Context window management** | Warning at 100K tokens, blocking at 128K (Streamlit) |
| **Feedback** | Every answer auto-scored 10/10; users can lower it with a 5-star widget |
| **Langfuse tracing** | Optional traces for sessions, generations and feedback scores |
| **Issue CRUD** | Browse (paginated), create, edit, delete issues via Streamlit UI |
| **Excel import** | Bulk import from Excel with auto-created teams/lines/machines |

## Project Structure

```
machine-issue-solver/
├── agent/                      # Sub-project 1: the agent (AG-UI + Streamlit)
│   ├── app/
│   │   ├── main.py             # AG-UI server (FastAPI, port 8123)
│   │   ├── agent.py            # compiled graph (create_react_agent)
│   │   ├── graph.py            # SYSTEM_PROMPT, search_issues, solve_issue_stream
│   │   ├── llm.py              # get_chat_model() — OpenAI-compatible endpoint
│   │   ├── streamlit_app.py    # Chat UI + sidebar (port 8501)
│   │   ├── api_client.py       # Pooled HTTP client for Issue API
│   │   ├── config.py           # Configuration
│   │   ├── history.py          # Token estimation
│   │   ├── conversation_store.py  # JSON session storage
│   │   ├── feedback.py         # Star feedback widget
│   │   ├── logger.py           # Logging + Timer
│   │   ├── langfuse_setup.py   # Langfuse SDK utilities
│   │   └── pages/
│   │       └── 1_Issues.py     # Issue CRUD page
│   ├── .env.example
│   ├── requirements.txt
│   ├── Dockerfile              # one image, both entrypoints
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
| Chat UI | Streamlit |
| API | FastAPI + Uvicorn |
| Database | PostgreSQL 16 + SQLAlchemy 2.0 (async) + asyncpg |
| HTTP client | httpx (pooled) |
| Tracing | Langfuse v4 (optional) |
| Excel processing | openpyxl |
| Containerization | Docker + Docker Compose |
