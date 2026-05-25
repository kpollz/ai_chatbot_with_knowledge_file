# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Gauss OpenAI-Compatible Proxy — a FastAPI server that translates between the **OpenAI Chat Completions API** and the internal **Company LLM (Gauss) API**. The key challenge is that Gauss only supports plain text (no native function calling, no vision, no reasoning tokens), so the proxy emulates OpenAI function calling via text-based `<tool_call >` tags.

Client (OpenClaw) sends standard OpenAI format, proxy translates to Gauss format, and vice versa.

## Commands

```bash
# Run locally (from repo root)
cd app && python main.py          # starts on http://localhost:9000

# Run with uvicorn directly
uvicorn app.main:app --host 0.0.0.0 --port 9000

# Run tests (from repo root)
pytest tests/

# Run a single test file
pytest tests/test_tool_translation.py

# Run a single test by name
pytest tests/test_tool_translation.py::test_function_name -v

# Docker
docker compose up -d              # build & start
docker compose logs -f            # view logs
docker compose down               # stop
```

Dependencies: `pip install -r requirements.txt` (fastapi, uvicorn, httpx, requests, pydantic, python-dotenv).

## Architecture

### Request Pipeline (7 steps)

Every `POST /v1/chat/completions` request flows through:

1. **Validate & Extract** — Pydantic parses body (`extra="ignore"` drops unknown fields)
2. **Normalize Messages** — `message_normalize.py`: content arrays → strings, `role: "developer"` → `"system"`, skip image parts
3. **Tool Translation (Request)** — `tool_translation.py`: `tools[]` → text prompt appended to system message; assistant `tool_calls` → `<tool_call >` text; `role: "tool"` → `[Tool Result]` text
4. **Flatten Messages** — `message_normalize.py`: split into `(input_value, system_message)` for Gauss
5. **Call Gauss** — `gauss_client.py`: POST to Company LLM API
6. **Tool Translation (Response)** — detect `<tool_call >` in response text → OpenAI `tool_calls` format
7. **Return Response** — format as OpenAI SSE stream or JSON

### Key Modules

| Module | Responsibility |
|--------|---------------|
| `app/main.py` | FastAPI endpoints, request pipeline orchestration, SSE streaming |
| `app/config.py` | Env vars, model registry (6 models with legacy name mapping), `get_model_config()` |
| `app/schemas.py` | Pydantic models for OpenAI request/response format |
| `app/message_normalize.py` | Content/role normalization, multi-turn message flattening |
| `app/tool_translation.py` | Tool calling emulation: `tools_to_prompt()`, `StreamingToolDetector`, `parse_tool_call_from_text()` |
| `app/gauss_client.py` | HTTP client for Company LLM — `call()` (non-streaming), `stream_call()` (streaming generator) |

### Tool Calling Emulation

This is the core complexity. Gauss returns plain text, so:

- **Request direction**: OpenAI `tools[]` are converted to a text prompt injected into the system message, instructing the LLM to use `<tool_call >{"name": "...", "arguments": {...}}</tool_call >` syntax
- **Response direction**: `StreamingToolDetector` is a state machine (`PASSTHROUGH` → `DETECTING_NAME` → `STREAMING_ARGS` → `CONSUMING_CLOSE`) that detects tool calls in streaming chunks and emits incremental SSE `tool_calls` deltas matching OpenAI's format

### Gauss API Format

The upstream Company LLM uses a proprietary format:
- Request: `{"component_inputs": {"<model-id>": {"input_value": "...", "system_message": "...", "parameters": "<json-string>", ...}}}`
- Streaming response: JSON-lines with `{"event": "token", "data": {"chunk": "..."}}`
- Auth via `x-api-key` header (not Bearer token)
- `parameters` field is a **JSON string**, not an object

## Configuration

Environment variables (see `.env.example`): `PROXY_HOST`, `PROXY_PORT`, `COMPANY_LLM_API_KEY` (required), `COMPANY_LLM_MODEL_ID`/`COMPANY_LLM_MODEL_URL` (optional overrides), `DEFAULT_TEMPERATURE`, `DEFAULT_TOP_P`, `REQUEST_TIMEOUT`, `SSL_VERIFY`, `LOG_LEVEL`, `TOOL_CALL_ENABLED`.

Model registry in `config.py` maps slug-style IDs (`gauss-2.3`, `gausso4`, etc.) to `model-id` and `model-url`. Legacy display names (`Gauss2.3`, `GaussO4`) are also supported via `_LEGACY_NAMES` mapping.

## Testing

Tests use `pytest` with `fastapi.testclient.TestClient` and `unittest.mock` to patch `gauss_client` calls — no real LLM connection needed. Tests cover message normalization, tool translation, schema validation, and full integration flows.
