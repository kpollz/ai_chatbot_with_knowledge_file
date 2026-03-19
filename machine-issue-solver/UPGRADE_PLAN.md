# Machine Issue Solver - Upgrade Plan & Feasibility Analysis

## Current State (AS-IS)

- **Architecture:** Streamlit app -> LangGraph (4 fixed nodes) -> direct SQLite queries + Company LLM
- **Flow:** Extract info (LLM) -> Validate -> Query DB (hardcoded SQL) -> Generate solution (LLM)
- **Problem:** Streamlit app contains BOTH SQL/database logic AND chatbot logic — tightly coupled
- **Limitations:** No message history, sync only, no feedback, no CRUD UI

## Target State (TO-BE)

**Two separate sub-projects (services):**

```
┌─────────────────────────────┐     HTTP API calls      ┌──────────────────────────────┐
│   Sub-project 1: Chatbot    │ ──────────────────────►  │  Sub-project 2: Issue API    │
│   (Streamlit app)           │  e.g. GET /issues?...    │  (FastAPI app)               │
│                             │ ◄──────────────────────  │                              │
│  - Chatbot logic only       │     JSON responses       │  - Issue CRUD logic only     │
│  - Calls Issue API via HTTP │                          │  - SQLite database access    │
│  - Message history          │                          │  - REST endpoints            │
│  - Feedback UI              │                          │  - Serves on localhost:8000  │
└─────────────────────────────┘                          └──────────────────────────────┘
```

- **Streamlit app** no longer contains any SQL code — it calls the Issue API over HTTP
- **FastAPI app** owns all database/SQL logic and exposes it as REST endpoints

---

## Decisions Made

| Decision | Choice | Reason |
|----------|--------|--------|
| Chatbot architecture | Keep current LangGraph 4-node flow | Defer tool-based agent; re-evaluate later |
| Service topology | 2 separate services (Streamlit + FastAPI) | Clean separation of concerns |
| Database | Keep SQLite | This is a demo project |
| Conversation storage | JSON files | Lightweight for demo; no extra DB needed |

---

## Requested Features

| # | Feature | Summary |
|---|---------|---------|
| F1 | Issue API (FastAPI) | Separate FastAPI service with CRUD endpoints for Issues, owning all DB logic |
| F2 | Chatbot calls API (not SQL) | Chatbot queries issues via HTTP calls to Issue API instead of direct SQL |
| F3 | Message history with context limit | Keep conversation history; handle 128K context window overflow |
| F4 | Async support | Non-blocking I/O for multi-user concurrency |
| F5 | Feedback mechanism (like/dislike) | Collect user feedback per response; store all conversations in JSON files |
| F6 | Issue CRUD UI | Streamlit page for users to manually browse/edit issues (calls Issue API) |

---

## Detailed Analysis

### F1 — Issue API (FastAPI Service)

**What:** Create a **separate FastAPI service** (Sub-project 2) that owns all database/SQL logic and exposes REST endpoints for Issues. Runs independently on `localhost:8000`.

**Scope:**
- Define Pydantic models for Issue, Machine, Line, Team
- Implement CRUD endpoints:
  - `POST /issues` — create
  - `GET /issues` — list/search (filter by machine_name, line_name)
  - `GET /issues/{id}` — get one
  - `PUT /issues/{id}` — update
  - `DELETE /issues/{id}` — delete
- Use async ORM (SQLAlchemy + aiosqlite or SQLModel) with existing SQLite database
- This is a standalone service — the Streamlit chatbot communicates with it over HTTP

**Feasibility:** HIGH — Standard backend work. No blockers.

**Effort:** Medium (~2-3 days)

**Risk:** Low. The current SQL query is simple; wrapping it in an API is straightforward.

---

### F2 — Chatbot Calls API Instead of Direct SQL

**What:** Keep the current LangGraph 4-node flow (extract -> validate -> query -> generate), but replace the direct SQLite query in `query_database_node` with an HTTP call to the Issue API from F1.

**Current flow:**
```
User query -> LLM extracts info -> if valid -> sqlite3.connect() + SQL query -> LLM generates answer
```

**New flow (same logic, different data source):**
```
User query -> LLM extracts info -> if valid -> HTTP GET localhost:8000/issues?... -> LLM generates answer
```

**Changes needed:**
- Remove `sqlite3` import and `query_machine_issues()` from chatbot code
- Replace with `httpx` call to `GET /issues?machine_name=X&line_name=Y`
- The chatbot sub-project has zero SQL code — it only knows about the API

**Note:** Tool-based agent (LLM decides when to call search) is deferred for future evaluation.

**Feasibility:** HIGH — Minimal change; swap SQL call for HTTP call.

**Effort:** Low (~1 day)

**Risk:** Low. The logic stays the same; only the data fetching mechanism changes.

---

### F3 — Message History with Context Window Management

**What:** Maintain conversation history per session. When approaching the 128K context limit, warn the user and ask them to start a new session.

**Sub-tasks:**
1. **Store messages in session** — Already partially done via `st.session_state.messages`. Need to also send history to LLM.
2. **Token counting** — Estimate token usage per message to track cumulative context size.
3. **Context overflow handling** — When approaching limit, show warning and block further messages.

**Token counting challenge:**
We don't have the Gauss tokenizer. Approaches:
- **Approximation:** Use `tiktoken` (OpenAI tokenizer) as rough estimate. For Vietnamese text, ~1-2 tokens per word. Set a conservative threshold (e.g., warn at 100K, block at 120K).
- **Character-based:** Simpler — ~4 characters per token for English, ~2-3 for Vietnamese. Less accurate but functional.
- **Ask API:** If the Company LLM API returns token usage in the response, use that (check the response format).

**Feasibility:** HIGH — Straightforward to implement. Token estimation is imprecise but workable.

**Effort:** Low-Medium (~1-2 days)

**Risk:** Low. Worst case: the approximation is off and users hit the limit slightly early or late. A conservative threshold mitigates this.

---

### F4 — Async Support

**What:** Make the codebase async for non-blocking I/O, improving multi-user concurrency.

**What needs to change:**
1. `company_chat_model.py` — Replace `requests` with `httpx.AsyncClient` (or `aiohttp`)
2. `graph.py` — Make node functions `async def`, use `await` for LLM calls and DB queries
3. Database layer — Use `aiosqlite` instead of `sqlite3`
4. FastAPI endpoints — Already async by default
5. Streamlit — Note: Streamlit already handles multi-user via separate sessions/threads. Async benefits are mainly for the FastAPI API layer.

**Important consideration:**
Streamlit itself is NOT async-native. It runs each user session in a separate thread. So async primarily benefits:
- The FastAPI CRUD API (if multiple users hit it simultaneously)
- Internal LLM calls (non-blocking while waiting for Gauss response)

For Streamlit, we can use `asyncio.run()` or `nest_asyncio` to bridge sync Streamlit with async backend code.

**Feasibility:** HIGH — All libraries have async equivalents.

**Effort:** Medium (~2-3 days). Touching most files, but changes are mechanical (sync -> async).

**Risk:** Low-Medium. Main risk is making sure the sync-to-async bridge works correctly in Streamlit. Well-documented patterns exist.

---

### F5 — Feedback Mechanism (Like/Dislike) + Conversation Storage

**What:**
- Each assistant response has a thumbs-up / thumbs-down button
- Default state: None (no vote)
- Store ALL conversations (messages + feedback) in **JSON files** for later analysis

**Sub-tasks:**
1. **JSON file structure for conversations:**
   ```json
   // conversations/session_{id}.json
   {
     "session_id": "uuid",
     "created_at": "2026-03-19T10:00:00",
     "messages": [
       {
         "message_id": "uuid",
         "role": "user",
         "content": "...",
         "timestamp": "...",
         "feedback": null  // null | "like" | "dislike"
       }
     ]
   }
   ```
2. **Streamlit UI:** Add like/dislike buttons below each assistant response
3. **Storage logic:** Save conversation to JSON file on each message exchange and feedback action
4. **Analysis:** JSON files can be loaded later for offline analysis (pandas, scripts, etc.)

**Why JSON files instead of DB:** This is a demo project. JSON files are simple to implement, easy to inspect manually, and require no additional database setup. Can migrate to DB later if needed.

**Streamlit challenge:**
Streamlit re-runs the entire script on every interaction. Adding buttons per message requires careful use of `st.session_state` and unique keys per message. This is doable but needs attention.

**Feasibility:** HIGH — Standard feature. JSON file I/O is trivial.

**Effort:** Medium (~2-3 days)

**Risk:** Low. The Streamlit button-per-message pattern is a bit tricky but many examples exist.

---

### F6 — Issue CRUD UI in Streamlit

**What:** A separate page/tab in Streamlit where users can manually browse, search, create, edit, and delete issues. Use case: user gets a chatbot answer, suspects it's wrong, goes to the Issue page to verify.

**Sub-tasks:**
1. **Multi-page Streamlit app** — Add a page for Issue Management alongside the Chat page
2. **List/Search issues** — Table view with filters (by machine, line)
3. **View issue detail** — Expand a row to see full details
4. **Create/Edit issue** — Form with fields: Machine, Line, Symptom, Cause, Solution
5. **Delete issue** — With confirmation dialog
6. All CRUD operations call the **Issue API** (F1) via HTTP — no direct SQL in Streamlit

**Feasibility:** HIGH — Streamlit has `st.data_editor`, `st.form`, multi-page support. All straightforward.

**Effort:** Medium (~2-3 days)

**Risk:** Low. Streamlit CRUD interfaces are well-supported.

---

## Dependency Graph

```
            ┌──────────────────── Sub-project 2 (Issue API) ─────────────────┐
            │                                                                 │
            │  F4 (Async) ──► F1 (CRUD API on localhost:8000)                │
            │                        │                                        │
            └────────────────────────┼────────────────────────────────────────┘
                                     │ HTTP
            ┌────────────────────────┼────────────────────────────────────────┐
            │                        ▼                                        │
            │  F2 (Chatbot calls API) ──► F3 (Message History)               │
            │         │                          │                            │
            │         ▼                          ▼                            │
            │  F6 (CRUD UI page)        F5 (Feedback + JSON storage)         │
            │                                                                 │
            └──────────────────── Sub-project 1 (Chatbot App) ───────────────┘
```

- **F4 (Async)** should be done first or alongside F1 — retrofitting async later means rewriting everything twice.
- **F1 (Issue API)** is the foundation — F2, F6 both depend on it being available at `localhost:8000`.
- **F2 (Chatbot calls API)** depends on F1 (replaces direct SQL with HTTP calls to Issue API).
- **F3 (Message History)** depends on F2 (needs the refactored chatbot).
- **F5 (Feedback)** depends on F3 (conversation storage feeds into feedback). Stores in JSON files.
- **F6 (CRUD UI)** depends on F1 (Streamlit page calls Issue API via HTTP).

---

## Recommended Implementation Phases

### Phase 1 — Issue API Service (F4 + F1)
> **Goal:** Standalone async FastAPI service for Issue CRUD, running on `localhost:8000`

**Tasks:**
1. Create sub-project 2 directory structure (`issue-api/`)
2. Set up FastAPI app with async configuration
3. Define SQLAlchemy/SQLModel models for Lines, Teams, Machines, Issues
4. Implement async CRUD service layer (aiosqlite)
5. Implement REST endpoints with Pydantic request/response models
6. Test all CRUD endpoints independently

**Deliverable:** Working standalone API at `localhost:8000/issues` with full CRUD

**Estimated effort:** 3-4 days

---

### Phase 2 — Chatbot Refactor (F2 + F3)
> **Goal:** Chatbot calls Issue API over HTTP instead of direct SQL; add message history

**Tasks:**
1. Remove all `sqlite3` / direct SQL code from chatbot sub-project
2. Replace `query_machine_issues()` with `httpx` call to `GET localhost:8000/issues?machine_name=X&line_name=Y`
3. Migrate `company_chat_model.py` to async (`httpx.AsyncClient`)
4. Make LangGraph nodes async
5. Implement message history:
   - Send conversation history to LLM
   - Track approximate token usage per message
   - Warn + block at 128K context threshold
6. Update Streamlit to manage history and bridge sync/async

**Deliverable:** Chatbot that fetches data from Issue API, remembers conversation, handles context limits

**Estimated effort:** 3-4 days

---

### Phase 3 — UX Features (F5 + F6)
> **Goal:** Feedback collection + Issue management UI

**Tasks:**
1. Implement JSON file conversation storage (auto-save on each exchange)
2. Add like/dislike buttons in Streamlit chat UI
3. Save feedback to conversation JSON files
4. Build multi-page Streamlit app (Chat page + Issues page)
5. Implement Issue list page with search/filter (calls `GET /issues`)
6. Implement Issue create/edit/delete forms (calls POST/PUT/DELETE endpoints)

**Deliverable:** Complete app with feedback and manual issue management

**Estimated effort:** 3-4 days

---

## Overall Feasibility Summary

| Feature | Feasibility | Effort | Risk | Priority |
|---------|------------|--------|------|----------|
| F1 — Issue API (FastAPI) | HIGH | Medium | Low | P0 (foundation) |
| F2 — Chatbot calls API | HIGH | Low | Low | P0 (core change) |
| F3 — Message History | HIGH | Low-Medium | Low | P1 |
| F4 — Async | HIGH | Medium | Low-Medium | P0 (do early) |
| F5 — Feedback + JSON storage | HIGH | Medium | Low | P2 |
| F6 — Issue CRUD UI | HIGH | Medium | Low | P2 |

**Total estimated effort:** 9-12 days (1 developer)

**Verdict: FULLY FEASIBLE.** All features use standard Python libraries. No major risks. The decision to keep the current chatbot logic and defer tool-based agent removes the previous medium-risk item.

---

## Proposed Project Structure (After Upgrade)

```
machine-issue-solver/
│
├── issue-api/                          # Sub-project 2: Issue API (FastAPI)
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                     # FastAPI entry point (uvicorn)
│   │   ├── config.py                   # API configuration
│   │   ├── database.py                 # SQLAlchemy async engine, session
│   │   ├── models.py                   # ORM models (Line, Team, Machine, Issue)
│   │   ├── schemas.py                  # Pydantic request/response schemas
│   │   ├── crud.py                     # CRUD operations
│   │   └── routes.py                   # REST endpoint definitions
│   ├── database/
│   │   └── issues.db                   # SQLite database (shared)
│   ├── requirements.txt
│   ├── .env.example
│   └── README.md
│
├── chatbot/                            # Sub-project 1: Chatbot (Streamlit)
│   ├── app/
│   │   ├── __init__.py
│   │   ├── config.py                   # Chatbot configuration
│   │   ├── company_chat_model.py       # Company LLM client (async)
│   │   ├── graph.py                    # LangGraph workflow (calls Issue API)
│   │   ├── api_client.py              # HTTP client for Issue API
│   │   ├── history.py                  # Message history & token management
│   │   ├── conversation_store.py       # JSON file storage for conversations
│   │   └── logger.py                   # Logging utility
│   ├── streamlit_app.py                # Streamlit entry point
│   ├── pages/
│   │   ├── 1_Chat.py                   # Chat page
│   │   └── 2_Issues.py                 # Issue CRUD page (calls Issue API)
│   ├── conversations/                  # JSON conversation files
│   │   └── session_xxx.json
│   ├── requirements.txt
│   ├── .env.example
│   └── README.md
│
├── UPGRADE_PLAN.md                     # This file
└── README.md                           # Root README (overview of both sub-projects)
```
