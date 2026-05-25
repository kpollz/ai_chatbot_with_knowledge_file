# Machine Issue Solver

AI-powered chatbot for diagnosing and resolving machine issues in a factory environment. Uses a ReAct Agent pattern with Company LLM (Gauss) and a FastAPI backend for issue data.

## Architecture

```
┌────────────────────────────────────┐          ┌─────────────────────────────────┐
│  Chatbot (Streamlit)               │   HTTP   │  Issue API (FastAPI)            │
│                                    │ ───────► │                                 │
│  - ReAct Agent (LangGraph)         │          │  - Async CRUD endpoints         │
│  - Streaming / Non-streaming LLM   │ ◄─────── │  - SQLAlchemy + aiosqlite      │
│  - Conversation history & feedback │   JSON   │  - SQLite database              │
│  - Issue CRUD UI page              │          │                                 │
│                                    │          │  localhost:8888                  │
│  localhost:8501                     │          └─────────────────────────────────┘
└────────────────────────────────────┘
```

Two independent services:
- **[Chatbot](chatbot/)** — Streamlit app with LLM-powered chat and issue management UI
- **[Issue API](issue-api/)** — FastAPI service owning all database access

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
```

### 2. Configure

```bash
# Chatbot config
cp chatbot/.env.example chatbot/.env
# Edit chatbot/.env → set COMPANY_LLM_API_KEY, MODEL_ID, MODEL_URL

# Issue API config
cp issue-api/.env.example issue-api/.env
# Edit issue-api/.env → set DB_PATH if needed
```

Place your SQLite database at `issue-api/database/issues.db`.

### 3. Run

```bash
# Terminal 1: Start Issue API
cd issue-api/app && python main.py

# Terminal 2: Start Chatbot
cd chatbot && streamlit run app/streamlit_app.py
```

- Chatbot UI: http://localhost:8501
- Issue API docs: http://localhost:8888/docs

## Features

| Feature | Description |
|---------|-------------|
| **ReAct Agent** | LLM reasons about queries and calls tools (search issues, list machines/lines) when needed |
| **Streaming mode** | Text appears word-by-word with step-by-step status updates |
| **Non-streaming mode** | Full response at once via LangGraph (toggle in sidebar) |
| **Conversation history** | Context maintained across turns with token estimation |
| **Context window management** | Warning at 100K tokens, blocking at 128K |
| **Feedback** | Like/dislike per response, saved to JSON |
| **Issue CRUD** | Browse, create, edit, delete issues via Streamlit UI |

## Project Structure

```
machine-issue-solver/
├── chatbot/                    # Sub-project 1: Streamlit Chatbot
│   ├── app/
│   │   ├── streamlit_app.py    # Chat UI + sidebar
│   │   ├── graph.py            # ReAct Agent (LangGraph + streaming)
│   │   ├── company_chat_model.py  # LangChain BaseChatModel for Company LLM
│   │   ├── api_client.py       # HTTP client for Issue API
│   │   ├── config.py           # Configuration
│   │   ├── history.py          # Token estimation
│   │   ├── conversation_store.py  # JSON session storage
│   │   ├── logger.py           # Logging + Timer
│   │   └── pages/
│   │       └── 1_Issues.py     # Issue CRUD page
│   ├── .env.example
│   ├── requirements.txt
│   └── README.md
│
├── issue-api/                  # Sub-project 2: FastAPI Issue Service
│   ├── app/
│   │   ├── main.py             # FastAPI entry point
│   │   ├── config.py           # Configuration
│   │   ├── database.py         # Async SQLAlchemy engine
│   │   ├── models.py           # ORM models
│   │   ├── schemas.py          # Pydantic schemas
│   │   ├── crud.py             # CRUD operations
│   │   └── routes.py           # REST endpoints
│   ├── database/               # SQLite database location
│   ├── .env.example
│   ├── requirements.txt
│   └── README.md
│
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
| Database | SQLite + SQLAlchemy (async) + aiosqlite |
| HTTP clients | httpx (async), requests (streaming) |
