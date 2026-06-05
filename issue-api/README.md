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
  FastAPI (async) ──► SQLAlchemy (async) ──► PostgreSQL (asyncpg)
```

## Database Schema

```
Team (id, name)
  └── Line (id, team_id, line_number)
        └── Machine (id, line_id, name, location, serial)
              └── Issue (id, machine_id, date, start_time, stop_time, total_time,
                          week, year, symptom, cause, solution, pic, user_input)
```

## API Endpoints

### Teams (read-only)
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/teams/` | List all teams |
| `GET` | `/teams/{id}` | Get a specific team |

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

### Issues (full CRUD + import)
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/issues/` | List issues (supports `skip` and `limit`) |
| `GET` | `/issues/search` | Search by `machine_name` + `line_name` (used by chatbot) |
| `GET` | `/issues/{id}` | Get a specific issue |
| `POST` | `/issues/` | Create a new issue |
| `POST` | `/issues/import` | Import issue (auto-creates Team/Line/Machine) |
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
│   ├── config.py     # Environment configuration
│   ├── database.py   # Async SQLAlchemy engine + session factory
│   ├── models.py     # ORM models: Team, Line, Machine, Issue
│   ├── schemas.py    # Pydantic request/response schemas
│   ├── crud.py       # Async CRUD operations
│   └── routes.py     # REST endpoint definitions
├── postgres_data/    # Docker PostgreSQL volume
├── .env.example
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── README.md
```

## Setup

```bash
cd issue-api
pip install -r requirements.txt
cp .env.example .env  # Edit if needed
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection URL (asyncpg) | `postgresql+asyncpg://postgres:postgres@localhost:5432/issue_api` |
| `DB_USER` | PostgreSQL user (for Docker) | `postgres` |
| `DB_PASSWORD` | PostgreSQL password (for Docker) | `postgres` |
| `DB_NAME` | PostgreSQL database name (for Docker) | `issue_api` |
| `DB_PORT` | PostgreSQL port (for Docker) | `5432` |
| `API_HOST` | Server bind address | `0.0.0.0` |
| `API_PORT` | Server port | `8888` |

## Run

### With Docker (recommended)

```bash
# Start PostgreSQL + API
docker-compose up -d

# View logs
docker-compose logs -f api

# Stop
docker-compose down

# Reset database (delete all data)
docker-compose down -v
docker-compose up -d
```

### Locally

```bash
cd app
python main.py
```

Or with uvicorn directly:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8888 --reload
```

API docs available at `http://localhost:8888/docs` (Swagger UI).

## Data Import

Use the root-level `import_excel.py` script to bulk-import factory data:

```bash
cd ..
python import_excel.py data.xlsx --api-url http://localhost:8888
```

The import endpoint auto-creates missing Team, Line, Machine records and skips duplicate issues (same machine + symptom).
