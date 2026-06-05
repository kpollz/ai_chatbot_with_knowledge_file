# Chatbot — Machine Issue Solver

Streamlit chatbot that answers questions about machine issues using a ReAct Agent pattern with Company LLM (Gauss).

## Architecture

```
User (Streamlit UI)
  │
  └── Streaming mode ──► solve_issue_stream() ──► LLM._stream() ──► Company LLM API (SSE)
                          (sync generator)         (requests)
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
- Both formats are detected via regex + `VALID_TOOLS` whitelist

Available tools:
| Tool | Description |
|------|-------------|
| `search_issues(machine_name, line_name, location?, serial?)` | Search issues for a specific machine on a line |
| `list_machines()` | List all machines in the database |
| `list_lines()` | List all production lines |

All tools call the **Issue API** over HTTP (no direct database access).

## Streaming Mode

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
- Full streamed text is sent to Langfuse as a single output after streaming completes

## Files

```
chatbot/
├── app/
│   ├── streamlit_app.py       # Streamlit UI (chat page, sidebar)
│   ├── graph.py               # ReAct Agent: streaming generator
│   ├── company_chat_model.py  # LangChain BaseChatModel for Company LLM
│   ├── api_client.py          # HTTP client for Issue API (sync + async)
│   ├── config.py              # Environment configuration
│   ├── history.py             # Token estimation & context window management
│   ├── conversation_store.py  # JSON file storage for conversations
│   ├── feedback.py            # Default-10 star feedback widget + Langfuse scores
│   ├── logger.py              # Logging + Timer context manager
│   ├── langfuse_setup.py      # Langfuse SDK v4 utilities
│   └── pages/
│       └── 1_Issues.py        # CRUD page for issue management
├── .env.example
├── Dockerfile
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
| `CONTEXT_WINDOW_LIMIT` | Max tokens before blocking input | `128000` |
| `CONTEXT_WARN_THRESHOLD` | Tokens before showing warning | `100000` |
| `LANGFUSE_PUBLIC_KEY` | Optional Langfuse public key | — |
| `LANGFUSE_SECRET_KEY` | Optional Langfuse secret key | — |
| `LANGFUSE_HOST` | Langfuse host URL | `https://cloud.langfuse.com` |

## Run

```bash
# Make sure Issue API is running first
streamlit run app/streamlit_app.py
```

The app runs on `http://localhost:8501` by default.

## Features

- **Chat with ReAct Agent** — LLM reasons about queries and calls tools when needed
- **Streaming responses** — Text appears word-by-word with step-by-step status updates
- **Conversation history** — Context maintained across turns within a session
- **Context window management** — Token estimation with warning/blocking thresholds
- **Default-10 feedback** — Every response is scored 10/10 by default; users can lower the score if the answer is unsatisfactory. Scores are sent to Langfuse.
- **Issue CRUD page** — Browse, create, edit, delete issues via Issue API
- **Session persistence** — Conversations auto-saved to `conversations/` as JSON
- **Langfuse tracing** — Optional trace collection for generations, tool executions and feedback
