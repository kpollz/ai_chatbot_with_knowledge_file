# Chatbot — Machine Issue Solver

Streamlit chatbot that answers questions about machine issues using a ReAct Agent pattern with Company LLM (Gauss).

## Architecture

```
User (Streamlit UI)
  │
  ├── Streaming mode ──► solve_issue_stream() ──► LLM._stream() ──► Company LLM API (SSE)
  │                       (sync generator)         (requests)
  │
  └── Non-streaming mode ► solve_issue() ──► LangGraph ReAct ──► LLM._agenerate() ──► Company LLM API
                           (async)           (ainvoke)            (httpx)
```

### ReAct Agent Flow

```
User query ──► Agent (LLM) ──► Has tool call? ──► YES ──► Execute tool ──► Agent (LLM) ──► Response
                                                  NO  ──► Direct response
```

The agent can loop up to 3 tool calls per query (configurable via `MAX_ITERATIONS`).

### Tool Calling

The Company LLM does not support native function calling. Tool calls are **text-based**:
- System prompt instructs LLM to output `<tool_call>JSON</tool_call>`
- Fast models may output raw JSON `{"tool": "...", "args": {...}}`
- Both formats are detected via regex + VALID_TOOLS whitelist

Available tools:
| Tool | Description |
|------|-------------|
| `search_issues(machine_name, line_name)` | Search issues for a specific machine on a line |
| `list_machines()` | List all machines in the database |
| `list_lines()` | List all production lines |

All tools call the **Issue API** over HTTP (no direct database access).

## Streaming vs Non-streaming

Toggle via sidebar or `STREAMING_ENABLED` env var.

| | Streaming | Non-streaming |
|---|-----------|---------------|
| **UX** | Text appears word-by-word with status updates | Full response at once with spinner |
| **Code path** | `solve_issue_stream()` — sync generator with prefix-buffer | `solve_issue()` — LangGraph `ainvoke` |
| **LLM call** | `_stream()` via `requests` (SSE) | `_agenerate()` via `httpx` |
| **Tool detection** | Buffer first 20 chars to detect `<tool_call>` prefix | LLM response parsed after completion |
| **Status updates** | Shows step-by-step: analyzing → searching → writing | Single spinner |

### Streaming Status Flow (with tool call)

```
⏳ Đang phân tích câu hỏi...              ← LLM call 1 (prefix-buffer)
⏳ Đang tìm kiếm vấn đề: CNC-01 trên Line 2...  ← Tool executing
⏳ Đang viết câu trả lời...               ← LLM call 2 starts
Máy CNC-01 trên Line 2 có các vấn đề...▌  ← Streaming text
```

## Files

```
chatbot/
├── app/
│   ├── streamlit_app.py       # Streamlit UI (chat page, sidebar, feedback)
│   ├── graph.py               # ReAct Agent: LangGraph + streaming generator
│   ├── company_chat_model.py  # LangChain BaseChatModel for Company LLM
│   ├── api_client.py          # HTTP client for Issue API (async + sync)
│   ├── config.py              # Environment configuration
│   ├── history.py             # Token estimation & context window management
│   ├── conversation_store.py  # JSON file storage for conversations
│   ├── logger.py              # Logging + Timer context manager
│   └── pages/
│       └── 1_Issues.py        # CRUD page for issue management
├── .env.example
└── requirements.txt
```

## Setup

```bash
cd chatbot
pip install -r requirements.txt
cp .env.example .env  # Edit with your credentials
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `ISSUE_API_URL` | Issue API base URL | `http://localhost:8888` |
| `LLM_MODEL` | Company LLM model name | `Gauss2.3` |
| `LLM_TEMPERATURE` | Sampling temperature | `0` |
| `COMPANY_LLM_API_KEY` | API key for Company LLM | — |
| `COMPANY_LLM_MODEL_ID` | Custom model ID (overrides model registry) | — |
| `COMPANY_LLM_MODEL_URL` | Custom model URL (overrides model registry) | — |
| `STREAMING_ENABLED` | Enable streaming mode by default | `true` |
| `CONTEXT_WINDOW_LIMIT` | Max tokens before blocking input | `128000` |
| `CONTEXT_WARN_THRESHOLD` | Tokens before showing warning | `100000` |

## Run

```bash
# Make sure Issue API is running first
streamlit run app/streamlit_app.py
```

The app runs on `http://localhost:8501` by default.

## Features

- **Chat with ReAct Agent** — LLM reasons about queries and calls tools when needed
- **Streaming / Non-streaming toggle** — Compare response modes in real-time
- **Conversation history** — Context maintained across turns within a session
- **Context window management** — Token estimation with warning/blocking thresholds
- **Feedback (like/dislike)** — Per-response feedback saved to JSON files
- **Issue CRUD page** — Browse, create, edit, delete issues via Issue API
- **Session persistence** — Conversations auto-saved to `conversations/` as JSON
