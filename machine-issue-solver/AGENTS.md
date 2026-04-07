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
│  - Streaming / Non-streaming LLM   │ ◄─────── │  - SQLAlchemy + asyncpg         │
│  - Conversation history & feedback │   JSON   │  - PostgreSQL database          │
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
| Database | PostgreSQL + SQLAlchemy (async) + asyncpg |
| HTTP clients | httpx (async), requests (streaming) |
| Tracing | Langfuse v4 (optional) |
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
│   │   ├── config.py           # Configuration (DATABASE_URL, host, port)
│   │   ├── database.py         # Async SQLAlchemy engine + session factory
│   │   ├── models.py           # ORM models: Team, Line, Machine, Issue
│   │   ├── schemas.py          # Pydantic request/response schemas
│   │   ├── crud.py             # Async CRUD operations
│   │   └── routes.py           # REST endpoint definitions
│   ├── database/               # SQLite database location (legacy)
│   ├── postgres_data/          # PostgreSQL data volume (Docker)
│   ├── Dockerfile              # Docker image for API
│   ├── docker-compose.yml      # PostgreSQL + API services
│   ├── MIGRATION.md            # SQLite to PostgreSQL migration guide
│   ├── .env.example            # Template for environment variables
│   ├── requirements.txt
│   └── README.md
│
├── import_excel.py             # Standalone script to import Excel data
├── fake_excel.py               # Generate test data for import testing
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
| `CONTEXT_WINDOW_LIMIT` | Max tokens before blocking input | `128000` |
| `CONTEXT_WARN_THRESHOLD` | Tokens before showing warning | `100000` |
| `LANGFUSE_PUBLIC_KEY` | Optional Langfuse public key | — |
| `LANGFUSE_SECRET_KEY` | Optional Langfuse secret key | — |
| `LANGFUSE_HOST` | Langfuse host URL | `https://cloud.langfuse.com` |

### Issue API (`issue-api/.env`)

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection URL | `postgresql+asyncpg://postgres:postgres@localhost:5432/issue_api` |
| `DB_USER` | PostgreSQL user (for Docker) | `postgres` |
| `DB_PASSWORD` | PostgreSQL password (for Docker) | `postgres` |
| `DB_NAME` | PostgreSQL database name (for Docker) | `issue_api` |
| `DB_PORT` | PostgreSQL port (for Docker) | `5432` |
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

# Install additional dependency for Excel import
pip install openpyxl
```

### Configuration

```bash
# Copy environment templates
cp chatbot/.env.example chatbot/.env
cp issue-api/.env.example issue-api/.env

# Edit chatbot/.env → set COMPANY_LLM_API_KEY, MODEL_ID, MODEL_URL
# Edit issue-api/.env → set DATABASE_URL if needed
```

### Run with Docker (Recommended for Issue API)

```bash
cd issue-api

# Start PostgreSQL and API
docker-compose up -d

# View logs
docker-compose logs -f api

# Stop
docker-compose down

# Reset database (delete all data)
docker-compose down -v
docker-compose up -d
```

### Run Locally (Development)

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
| `streamlit_app.py` | UI layout, session state, chat input handling, feedback collection |
| `graph.py` | ReAct agent logic (nodes, edges, routing), streaming generator, tool execution |
| `company_chat_model.py` | LangChain-compatible LLM wrapper (sync/async/stream) for Company LLM |
| `api_client.py` | All HTTP calls to Issue API (sync versions for streaming flow) |
| `config.py` | Centralized environment variable loading, model registry |
| `history.py` | Token estimation and context window management |
| `conversation_store.py` | JSON persistence for chat sessions in `conversations/` directory |
| `logger.py` | Logging configuration and Timer context manager |
| `pages/1_Issues.py` | Issue CRUD management UI (separate Streamlit page) |

### Issue API Module Responsibilities

| File | Purpose |
|------|---------|
| `main.py` | FastAPI app setup, CORS, router registration, lifespan events |
| `routes.py` | API endpoint definitions (teams, lines, machines, issues) |
| `crud.py` | Database operations (async SQLAlchemy) |
| `models.py` | SQLAlchemy ORM models |
| `schemas.py` | Pydantic models for request/response validation |
| `database.py` | Async engine and session management |
| `config.py` | Environment configuration |

## Key Implementation Details

### Database Schema (PostgreSQL)

```
Team (id, name, created_at)
  └── Line (id, team_id, line_number, created_at)
        └── Machine (id, line_id, name, location, serial, created_at)
              └── Issue (id, machine_id, date, start_time, stop_time, total_time,
                         week, year, hien_tuong, nguyen_nhan, khac_phuc, pic, user_input, created_at)
```

**Note**: Vietnamese field names (`hien_tuong` = symptom, `nguyen_nhan` = cause, `khac_phuc` = solution) are used because they map directly to the existing factory data format.

### ReAct Agent Flow

The agent uses **text-based tool calling** (no native function calling required):

1. User query → Agent (LLM)
2. LLM decides: direct answer OR tool call
3. Tool call format: `<tool_call>{"tool": "...", "args": {...}}</tool_call>`
4. If tool called → execute → feed result back to LLM → final answer
5. Maximum 3 iterations (configurable via `MAX_ITERATIONS`)

Available tools:
- `search_issues(machine_name, line_name, location?, serial?)`

### Streaming Mode

The chatbot uses a custom streaming implementation:

**Flow:**
```
⏳ Đang phân tích câu hỏi...              ← LLM call 1 (prefix-buffer)
⏳ Đang tìm kiếm vấn đề: CNC-01 trên Line 2...  ← Tool executing
⏳ Đang viết câu trả lời...               ← LLM call 2 starts
Máy CNC-01 trên Line 2 có các vấn đề...▌  ← Streaming text
```

**Key features:**
- Uses sync `requests` library for SSE (Server-Sent Events)
- Prefix-buffer (20 chars) detects `<tool_call>` in first response chunk
- Status updates show agent progress
- Event types: `{"type": "status", "message": "..."}` or `{"type": "chunk", "text": "..."}`

### Token Estimation

Context window management uses character-based approximation:
- Vietnamese text: ~2-3 characters per token
- English text: ~4 characters per token
- Conservative estimate: ~3 chars/token

Warning at 100K tokens, blocking at 128K tokens.

## Development Conventions

### Code Style

- **Python**: Standard PEP 8
- **Imports**: Grouped by stdlib, third-party, local (with sys.path insertion for pages)
- **Async**: Use `async/await` for all database and HTTP operations in Issue API
- **Type Hints**: Use throughout (especially in `schemas.py` and function signatures)
- **Logging**: Use the centralized `logger` from `logger.py` with Timer context manager for timing

### Error Handling

- **Chatbot**: Catch exceptions, log errors, show user-friendly messages in UI
- **Issue API**: Use FastAPI's `HTTPException` with appropriate status codes:
  - 404: Resource not found
  - 409: Conflict (duplicate resource)
  - 400: Bad request
  - 422: Validation error

### Database Patterns

- All database operations are async using SQLAlchemy 2.0+ syntax
- Use `select()`, `async_session()` context managers
- Case-insensitive search using `func.lower()`
- Foreign key constraints with `ondelete="CASCADE"`

## Testing Strategy

This project currently does not have automated tests. Manual testing workflow:

1. **API Testing**: Use Swagger UI at `http://localhost:8888/docs`
2. **Chat Testing**: Use the Streamlit UI with sample queries:
   - "Toi can giai phap cho may CNC-01 tren Line 2"
   - "Machine Robot Arm o Line 1 bi loi gi?"
   - "Co nhung may nao trong he thong?"
3. **Import Testing**: Use `fake_excel.py` to generate test data:
   ```bash
   python fake_excel.py test_data.xlsx --rows 50
   python import_excel.py test_data.xlsx --dry-run
   python import_excel.py test_data.xlsx
   ```

## Data Import

Use `import_excel.py` to import factory data from Excel files:

```bash
# Dry run (no data written)
python import_excel.py data.xlsx --dry-run

# Import with custom API URL
python import_excel.py data.xlsx --api-url http://localhost:8888

# Import starting from specific row
python import_excel.py data.xlsx --start-row 5
```

Excel columns expected (in order):
```
STT, Line, Team, Machine, Location, Serial, Date, Start Time, Stop Time,
Total Time, Week, Year, Hiện tượng, Nguyên nhân, Khắc phục, PIC, User Input
```

The import endpoint (`POST /issues/import`) auto-creates Team, Line, Machine if not found and skips duplicate issues (same machine + symptom).

## Security Considerations

- API keys are stored in `.env` files (never commit these)
- CORS is configured to allow all origins (`["*"]`) — tighten for production
- PostgreSQL credentials in Docker via environment variables
- SSL verification is disabled (`verify=False`) for Company LLM API calls — review for production
- Conversation files saved locally in `conversations/` directory

## Common Tasks for Agents

### Adding a New Tool to the Agent

1. Add tool function in `api_client.py` (sync version for streaming)
2. Add endpoint in `issue-api/app/routes.py`
3. Add CRUD function in `issue-api/app/crud.py`
4. Update `VALID_TOOLS` and `SYSTEM_PROMPT` in `chatbot/app/graph.py`
5. Add tool execution in `_execute_tool_sync()` in `graph.py`

### Adding a New Page to Streamlit

1. Create file in `chatbot/app/pages/2_PageName.py` (number prefix controls order)
2. Add `sys.path.insert(0, str(Path(__file__).parent.parent))` at top
3. Use `st.set_page_config()` and standard Streamlit patterns

### Modifying the Database Schema

1. Update `models.py` with new column/model
2. Update corresponding Pydantic schemas in `schemas.py`
3. Update CRUD operations in `crud.py`
4. Update API endpoints in `routes.py` if needed
5. For Docker: `docker-compose down -v && docker-compose up -d` to recreate tables
6. For local PostgreSQL: run migration manually or recreate database

## Migration History

The project was migrated from SQLite to PostgreSQL:

| Aspect | SQLite (Legacy) | PostgreSQL (Current) |
|--------|-----------------|----------------------|
| Schema | Lines → Teams → Machines | Team → Line → Machine |
| Driver | aiosqlite | asyncpg |
| Concurrent writes | Limited | Full support |
| Text search | Basic | Full-text capable |
| Case sensitivity | Default | Configurable |

See `issue-api/MIGRATION.md` for detailed migration notes.

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
| Docker setup | `issue-api/docker-compose.yml` |
| Excel import | `import_excel.py` |
| Test data generation | `fake_excel.py` |
