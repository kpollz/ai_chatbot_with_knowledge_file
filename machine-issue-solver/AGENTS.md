# Machine Issue Solver — AI Agent Guide

This guide helps AI coding agents understand and work with this project effectively.

## Project Overview

**Machine Issue Solver** is an AI-powered chatbot system for diagnosing and resolving machine issues in a factory environment. It uses a ReAct Agent pattern with Company LLM (Gauss) and consists of two independent services that communicate via HTTP.

### Architecture

```
┌────────────────────────────────────┐          ┌─────────────────────────────────┐
│  Chatbot (Streamlit)               │   HTTP   │  Issue API (FastAPI)            │
│                                    │ ───────► │                                 │
│  - ReAct Agent (LangGraph)         │          │  - Async CRUD endpoints         │
│  - Streaming / Non-streaming LLM   │ ◄─────── │  - SQLAlchemy + aiosqlite       │
│  - Conversation history & feedback │   JSON   │  - SQLite database              │
│  - Issue CRUD UI page              │          │                                 │
│                                    │          │  localhost:8888                 │
│  localhost:8501                    │          └─────────────────────────────────┘
└────────────────────────────────────┘
```

**Language**: Project code is in English, but user-facing content is primarily Vietnamese (factory workers in Vietnam are the target users).

## Technology Stack

| Component | Technology |
|-----------|-----------|
| LLM | Company LLM (Gauss 2.3 / GaussO Flash / GaussO4) |
| Agent framework | LangGraph + LangChain |
| Chat UI | Streamlit |
| API | FastAPI + Uvicorn |
| Database | SQLite + SQLAlchemy (async) + aiosqlite |
| HTTP clients | httpx (async), requests (streaming) |
| Environment | python-dotenv |

## Project Structure

```
machine-issue-solver/
├── chatbot/                    # Sub-project 1: Streamlit Chatbot
│   ├── app/
│   │   ├── streamlit_app.py    # Main entry: Chat UI + sidebar
│   │   ├── graph.py            # ReAct Agent (LangGraph + streaming)
│   │   ├── company_chat_model.py  # LangChain BaseChatModel for Company LLM
│   │   ├── api_client.py       # HTTP client for Issue API
│   │   ├── config.py           # Environment configuration
│   │   ├── history.py          # Token estimation & context window management
│   │   ├── conversation_store.py  # JSON file storage for conversations
│   │   ├── logger.py           # Logging + Timer context manager
│   │   └── pages/
│   │       └── 1_Issues.py     # Issue CRUD management page
│   ├── .env.example            # Template for environment variables
│   ├── requirements.txt
│   └── README.md
│
├── issue-api/                  # Sub-project 2: FastAPI Issue Service
│   ├── app/
│   │   ├── main.py             # FastAPI entry point
│   │   ├── config.py           # Configuration (DB_PATH, host, port)
│   │   ├── database.py         # Async SQLAlchemy engine + session factory
│   │   ├── models.py           # ORM models: Line, Team, Machine, Issue
│   │   ├── schemas.py          # Pydantic request/response schemas
│   │   ├── crud.py             # Async CRUD operations
│   │   └── routes.py           # REST endpoint definitions
│   ├── database/               # SQLite database location
│   │   └── issues.db           # Place your database here
│   ├── .env.example            # Template for environment variables
│   ├── requirements.txt
│   └── README.md
│
├── streaming_sample.py         # Standalone script demonstrating LLM streaming
├── .gitignore
└── README.md                   # Main project documentation
```

## Configuration

### Chatbot (`chatbot/.env`)

| Variable | Description | Default |
|----------|-------------|---------|
| `ISSUE_API_URL` | Issue API base URL | `http://localhost:8888` |
| `LLM_MODEL` | Company LLM model name | `Gauss2.3` |
| `LLM_TEMPERATURE` | Sampling temperature | `0` |
| `COMPANY_LLM_API_KEY` | **Required** API key for Company LLM | — |
| `COMPANY_LLM_MODEL_ID` | Custom model ID (overrides registry) | — |
| `COMPANY_LLM_MODEL_URL` | Custom model URL (overrides registry) | — |
| `STREAMING_ENABLED` | Enable streaming mode by default | `true` |
| `CONTEXT_WINDOW_LIMIT` | Max tokens before blocking input | `128000` |
| `CONTEXT_WARN_THRESHOLD` | Tokens before showing warning | `100000` |

### Issue API (`issue-api/.env`)

| Variable | Description | Default |
|----------|-------------|---------|
| `DB_PATH` | Path to SQLite database file | `./database/issues.db` |
| `API_HOST` | Server bind address | `0.0.0.0` |
| `API_PORT` | Server port | `8888` |

## Build and Run Commands

### Setup (one-time)

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies for both sub-projects
pip install -r chatbot/requirements.txt
pip install -r issue-api/requirements.txt
```

### Configuration

```bash
# Copy environment templates
cp chatbot/.env.example chatbot/.env
cp issue-api/.env.example issue-api/.env

# Edit chatbot/.env → set COMPANY_LLM_API_KEY, MODEL_ID, MODEL_URL
# Edit issue-api/.env → set DB_PATH if needed
```

### Run Services

**Terminal 1 — Start Issue API:**
```bash
cd issue-api/app && python main.py
# Or with uvicorn: uvicorn app.main:app --host 0.0.0.0 --port 8888 --reload
```

**Terminal 2 — Start Chatbot:**
```bash
cd chatbot && streamlit run app/streamlit_app.py
```

### Access Points

- Chatbot UI: http://localhost:8501
- Issue API docs: http://localhost:8888/docs

## Code Organization Patterns

### Chatbot Module Responsibilities

| File | Purpose |
|------|---------|
| `streamlit_app.py` | UI layout, session state, chat input handling |
| `graph.py` | ReAct agent logic (nodes, edges, routing), streaming generator |
| `company_chat_model.py` | LangChain-compatible LLM wrapper (sync/async/stream) |
| `api_client.py` | All HTTP calls to Issue API (async + sync versions) |
| `config.py` | Centralized environment variable loading |
| `history.py` | Token estimation and context window management |
| `conversation_store.py` | JSON persistence for chat sessions |

### Issue API Module Responsibilities

| File | Purpose |
|------|---------|
| `main.py` | FastAPI app setup, CORS, router registration |
| `routes.py` | API endpoint definitions (lines, teams, machines, issues) |
| `crud.py` | Database operations (async SQLAlchemy) |
| `models.py` | SQLAlchemy ORM models |
| `schemas.py` | Pydantic models for request/response validation |
| `database.py` | Async engine and session management |

## Key Implementation Details

### ReAct Agent Flow

The agent uses **text-based tool calling** (no native function calling required):

1. User query → Agent (LLM)
2. LLM decides: direct answer OR tool call
3. Tool call format: `<tool_call>{"tool": "...", "args": {...}}</tool_call>`
4. If tool called → execute → feed result back to LLM → final answer
5. Maximum 3 iterations (configurable via `MAX_ITERATIONS`)

Available tools:
- `search_issues(machine_name, line_name, location?, serial?)`
- `list_machines()`
- `list_lines()`

### Streaming Mode

The chatbot supports two response modes:

**Streaming (default):**
- Text appears word-by-word
- Status updates: "Đang phân tích..." → "Đang tìm kiếm..." → "Đang viết..."
- Uses sync `requests` library for SSE (Server-Sent Events)
- Prefix-buffer detects `<tool_call>` in first 20 chars

**Non-streaming:**
- Full response at once with spinner
- Uses async `httpx` via LangGraph `ainvoke`

### Database Schema

```
Lines (LineID, LineName)
  └── Teams (TeamID, TeamName, LineID)
        └── Machines (MachineID, MachineName, Location, Serial, TeamID)
              └── Issues (IssueID, MachineID, Date, Start Time, Total Time,
                          Week, Year, Hiện tượng, Nguyên nhân, Khắc phục, PIC, User Input)
```

Note: Vietnamese field names (`Hiện tượng` = symptom, `Nguyên nhân` = cause, `Khắc phục` = solution) are used because they map directly to the existing factory data format.

## Development Conventions

### Code Style

- **Python**: Standard PEP 8
- **Imports**: Grouped by stdlib, third-party, local (with sys.path insertion for pages)
- **Async**: Use `async/await` for all database and HTTP operations
- **Logging**: Use the centralized `logger` from `logger.py` with Timer context manager for timing

### Error Handling

- Chatbot: Catch exceptions, log errors, show user-friendly messages in UI
- Issue API: Use FastAPI's `HTTPException` with appropriate status codes (404, 409, etc.)

### Type Hints

- Use Python type hints throughout (especially in `schemas.py` and function signatures)
- Pydantic models for all request/response validation

## Testing Strategy

This project currently does not have automated tests. Manual testing workflow:

1. **API Testing**: Use Swagger UI at `http://localhost:8888/docs`
2. **Chat Testing**: Use the Streamlit UI with sample queries:
   - "Toi can giai phap cho may CNC-01 tren Line 2"
   - "Machine Robot Arm o Line 1 bi loi gi?"
   - "Co nhung may nao trong he thong?"

## Security Considerations

- API keys are stored in `.env` files (never commit these)
- CORS is configured to allow all origins (`["*"]`) — tighten for production
- SQLite database files are gitignored
- SSL verification is disabled (`verify=False`) for Company LLM API calls — review for production

## Common Tasks for Agents

### Adding a New Tool to the Agent

1. Add tool function in `api_client.py` (both async and sync versions)
2. Add endpoint in `issue-api/app/routes.py`
3. Add CRUD function in `issue-api/app/crud.py`
4. Update `VALID_TOOLS` and `SYSTEM_PROMPT` in `chatbot/app/graph.py`
5. Add tool execution in `tool_node()` and `_execute_tool_sync()`

### Adding a New Page to Streamlit

1. Create file in `chatbot/app/pages/2_PageName.py` (number prefix controls order)
2. Add `sys.path.insert(0, str(Path(__file__).parent.parent))` at top
3. Use `st.set_page_config()` and standard Streamlit patterns

### Modifying the Database Schema

1. Update `models.py` with new column/model
2. Update corresponding Pydantic schemas in `schemas.py`
3. Update CRUD operations in `crud.py`
4. Update API endpoints in `routes.py` if needed
5. Run database migration manually (SQLite has no built-in migrations)

## File Locations Quick Reference

| What you need | Where to look |
|---------------|---------------|
| Environment variables | `chatbot/config.py`, `issue-api/config.py` |
| LLM model configuration | `chatbot/config.py` (COMPANY_MODELS dict) |
| API endpoint definitions | `issue-api/app/routes.py` |
| Database queries | `issue-api/app/crud.py` |
| Agent behavior/prompt | `chatbot/app/graph.py` (SYSTEM_PROMPT) |
| UI layout | `chatbot/app/streamlit_app.py` |
| Issue management UI | `chatbot/app/pages/1_Issues.py` |
