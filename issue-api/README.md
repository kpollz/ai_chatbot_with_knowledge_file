# Issue API — Machine Issue Database Service

Async FastAPI service that provides CRUD access to the machine issue database. Used by the Chatbot as its data backend.

## Architecture

```
Chatbot (HTTP client)
  │
  ├── GET /issues/search?machine_name=X&line_name=Y   ← Chatbot agent tool
  ├── GET /machines/                                    ← Chatbot agent tool
  ├── GET /lines/                                       ← Chatbot agent tool
  │
  └── GET/POST/PUT/DELETE /issues/...                   ← Streamlit CRUD page
        │
        ▼
  FastAPI (async) ──► SQLAlchemy (async) ──► SQLite (aiosqlite)
```

## Database Schema

```
Lines (LineID, LineName)
  └── Teams (TeamID, TeamName, LineID)
        └── Machines (MachineID, MachineName, Location, Serial, TeamID)
              └── Issues (IssueID, MachineID, Date, Start Time, Total Time,
                          Week, Year, Hiện tượng, Nguyên nhân, Khắc phục, PIC, User Input)
```

## API Endpoints

### Lines (read-only)
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/lines/` | List all production lines |
| `GET` | `/lines/{id}` | Get a specific line |

### Machines (read-only)
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/machines/` | List all machines |
| `GET` | `/machines/{id}` | Get a specific machine |

### Issues (full CRUD)
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/issues/` | List issues (supports `skip` and `limit` query params) |
| `GET` | `/issues/search` | Search by `machine_name` + `line_name` (used by chatbot) |
| `GET` | `/issues/{id}` | Get a specific issue |
| `POST` | `/issues/` | Create a new issue |
| `PUT` | `/issues/{id}` | Update an existing issue |
| `DELETE` | `/issues/{id}` | Delete an issue |

### Health
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |

## Files

```
issue-api/
├── app/
│   ├── main.py       # FastAPI entry point + CORS middleware
│   ├── config.py     # Environment configuration (DB_PATH, host, port)
│   ├── database.py   # Async SQLAlchemy engine + session factory
│   ├── models.py     # ORM models: Line, Team, Machine, Issue
│   ├── schemas.py    # Pydantic request/response schemas
│   ├── crud.py       # Async CRUD operations
│   └── routes.py     # REST endpoint definitions
├── database/
│   └── .gitkeep      # Place issues.db here
├── .env.example
└── requirements.txt
```

## Setup

```bash
cd issue-api
pip install -r requirements.txt
cp .env.example .env  # Edit if needed
```

Place your SQLite database file at `database/issues.db`.

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DB_PATH` | Path to SQLite database file | `./database/issues.db` |
| `API_HOST` | Server bind address | `0.0.0.0` |
| `API_PORT` | Server port | `8888` |

## Run

```bash
cd app
python main.py
```

Or with uvicorn directly:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8888 --reload
```

API docs available at `http://localhost:8888/docs` (Swagger UI).
