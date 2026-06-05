# Machine Issue Solver

AI-powered chatbot for diagnosing and resolving machine issues in a factory environment. Uses a ReAct Agent pattern with Company LLM (Gauss) and a FastAPI backend for issue data.

## Architecture

```
┌────────────────────────────────────┐          ┌─────────────────────────────────┐
│  Chatbot (Streamlit)               │   HTTP   │  Issue API (FastAPI)            │
│                                    │ ───────► │                                 │
│  - ReAct Agent (LangGraph)         │          │  - Async CRUD endpoints         │
│  - Streaming LLM                   │ ◄─────── │  - SQLAlchemy + asyncpg         │
│  - Conversation history & feedback │   JSON   │  - PostgreSQL database          │
│  - Issue CRUD UI page              │          │                                 │
│                                    │          │  localhost:8888                 │
│  localhost:8501                    │          └─────────────────────────────────┘
└────────────────────────────────────┘                    ▲
                                                          │
                                               ┌──────────┴──────────┐
                                               │  PostgreSQL 16      │
                                               │  (Docker volume)    │
                                               └─────────────────────┘
```

Three services managed from the repo root:
- **[Chatbot](chatbot/)** — Streamlit app with LLM-powered chat and issue management UI
- **[Issue API](issue-api/)** — FastAPI service owning all database access
- **PostgreSQL** — Relational database for teams, lines, machines and issues

## Quick Start

### 1. Setup

```bash
# Clone and enter project
cd machine-issue-solver

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install both sub-projects
pip install -r chatbot/requirements.txt
pip install -r issue-api/requirements.txt
pip install openpyxl
```

### 2. Configure

```bash
# Chatbot config
cp chatbot/.env.example chatbot/.env
# Edit chatbot/.env → set COMPANY_LLM_API_KEY, COMPANY_LLM_MODEL_ID, COMPANY_LLM_MODEL_URL

# Issue API config
cp issue-api/.env.example issue-api/.env
# Edit issue-api/.env → set DATABASE_URL if needed
```

### 3. Run with Docker (recommended)

```bash
# Start PostgreSQL + Issue API + Chatbot
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

### 4. Run locally for development

```bash
# Terminal 1: Start PostgreSQL (or use the issue-api/docker-compose.yml)
cd issue-api && docker-compose up -d postgres

# Terminal 2: Start Issue API
cd issue-api/app && python main.py

# Terminal 3: Start Chatbot
cd chatbot && streamlit run app/streamlit_app.py
```

Access points:
- Chatbot UI: http://localhost:8501
- Issue API docs: http://localhost:8888/docs

## Features

| Feature | Description |
|---------|-------------|
| **ReAct Agent** | LLM reasons about queries and calls `search_issues` when needed |
| **Streaming mode** | Text appears word-by-word with step-by-step status updates |
| **Conversation history** | Context maintained across turns with token estimation |
| **Context window management** | Warning at 100K tokens, blocking at 128K |
| **Feedback** | Default 10/10 star rating; users can lower the score if needed |
| **Langfuse tracing** | Optional trace collection for sessions, generations and feedback scores |
| **Issue CRUD** | Browse (paginated), create, edit, delete issues via Streamlit UI |
| **Excel import** | Bulk import from Excel with auto-created teams/lines/machines |

## Project Structure

```
machine-issue-solver/
├── chatbot/                    # Sub-project 1: Streamlit Chatbot
│   ├── app/
│   │   ├── streamlit_app.py    # Chat UI + sidebar
│   │   ├── graph.py            # ReAct Agent (streaming generator)
│   │   ├── company_chat_model.py  # LangChain BaseChatModel for Company LLM
│   │   ├── api_client.py       # HTTP client for Issue API
│   │   ├── config.py           # Configuration
│   │   ├── history.py          # Token estimation
│   │   ├── conversation_store.py  # JSON session storage
│   │   ├── feedback.py         # Default-10 feedback widget
│   │   ├── logger.py           # Logging + Timer
│   │   ├── langfuse_setup.py   # Langfuse SDK utilities
│   │   └── pages/
│   │       └── 1_Issues.py     # Issue CRUD page
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
├── import_excel.py             # Standalone Excel data importer
├── fake_excel.py               # Generate fake test data
├── streaming_sample.py         # Standalone LLM streaming demo
├── docker-compose.yml          # Full-stack compose
├── .gitignore
└── README.md                   # This file
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| LLM | Company LLM (Gauss 2.3 / GaussO Flash / GaussO4) |
| Agent framework | LangGraph + LangChain |
| Chat UI | Streamlit |
| API | FastAPI + Uvicorn |
| Database | PostgreSQL 16 + SQLAlchemy 2.0 (async) + asyncpg |
| HTTP clients | httpx (async), requests (streaming) |
| Tracing | Langfuse v4 (optional) |
| Excel processing | openpyxl |
| Containerization | Docker + Docker Compose |
