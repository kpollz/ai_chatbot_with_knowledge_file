"""
Gauss OpenAI-Compatible Proxy — FastAPI Server

Translates between OpenAI Chat Completions API and Company LLM (Gauss) API.
See API_CONTRACT.md for full schema details.
"""

import json
import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

import gauss_client
from config import (
    COMPANY_LLM_API_KEY,
    COMPANY_MODELS,
    DEFAULT_TEMPERATURE,
    DEFAULT_TOP_P,
    LOG_LEVEL,
    PROXY_HOST,
    PROXY_PORT,
    get_model_config,
)
from schemas import (
    ChatCompletionChunk,
    ChatCompletionRequest,
    ChatCompletionResponse,
    Choice,
    DeltaMessage,
    ErrorDetail,
    ErrorResponse,
    ModelListResponse,
    ModelObject,
    ResponseMessage,
    StreamChoice,
    Usage,
)

# ── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("gauss-proxy")

# ── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Gauss OpenAI-Compatible Proxy",
    description="Translates OpenAI Chat Completions API to Company LLM (Gauss) API",
    version="1.0.0",
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _generate_id() -> str:
    return f"chatcmpl-{uuid.uuid4().hex[:12]}"


def _extract_api_key(request: Request) -> str | None:
    """Extract API key from Authorization: Bearer <key> header."""
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return None


def _flatten_messages(messages: list) -> tuple[str, str]:
    """Flatten OpenAI messages array into (input_value, system_message).

    Ref: company_chat_model.py _parse_messages() lines 73-86
    Behavior:
      - system role  -> system_message (last one wins)
      - single user message -> use directly as input_value
      - multi-turn   -> formatted conversation string
    """
    system_message = ""
    non_system = []

    for msg in messages:
        if msg.role == "system":
            system_message = msg.content
        else:
            non_system.append(msg)

    if not non_system:
        return "", system_message

    # Single user message -> use directly (no prefix needed)
    if len(non_system) == 1 and non_system[0].role == "user":
        return non_system[0].content, system_message

    # Multi-turn -> formatted conversation
    role_map = {"user": "User", "assistant": "Assistant"}
    parts = []
    for msg in non_system:
        prefix = role_map.get(msg.role, msg.role.capitalize())
        parts.append(f"{prefix}: {msg.content}")

    return "\n".join(parts), system_message


def _error_json(status: int, message: str, error_type: str = "server_error",
                code: str | None = None) -> JSONResponse:
    """Return an OpenAI-format error response."""
    body = ErrorResponse(error=ErrorDetail(message=message, type=error_type, code=code))
    return JSONResponse(status_code=status, content=body.model_dump())


# ── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


@app.get("/v1/models")
async def list_models():
    now = int(time.time())
    data = [
        ModelObject(id=name, created=now)
        for name in COMPANY_MODELS
    ]
    return ModelListResponse(data=data)


@app.post("/v1/chat/completions")
async def chat_completions(body: ChatCompletionRequest, request: Request):
    # ── Auth ─────────────────────────────────────────────────────────────
    api_key = _extract_api_key(request) or COMPANY_LLM_API_KEY
    if not api_key:
        return _error_json(401, "Missing API key. Provide Authorization: Bearer <key> header "
                           "or set COMPANY_LLM_API_KEY env var.",
                           error_type="authentication_error")

    # ── Model lookup ─────────────────────────────────────────────────────
    model_config = get_model_config(body.model)
    if not model_config:
        return _error_json(404, f"Model not found: {body.model}",
                           error_type="invalid_request_error", code="model_not_found")

    # ── Messages validation & flattening ─────────────────────────────────
    if not body.messages:
        return _error_json(400, "messages is required and must not be empty",
                           error_type="invalid_request_error")

    input_value, system_message = _flatten_messages(body.messages)
    if not input_value:
        return _error_json(400, "At least one non-system message is required",
                           error_type="invalid_request_error")

    # ── Parameters ───────────────────────────────────────────────────────
    temperature = body.temperature if body.temperature is not None else DEFAULT_TEMPERATURE
    top_p = body.top_p if body.top_p is not None else DEFAULT_TOP_P
    model_url = model_config["model-url"]
    model_id = model_config["model-id"]

    logger.info(f"Request: model={body.model}, stream={body.stream}, "
                f"messages={len(body.messages)}")

    # ── Streaming ────────────────────────────────────────────────────────
    if body.stream:
        return StreamingResponse(
            _stream_generator(
                model_url=model_url,
                model_id=model_id,
                api_key=api_key,
                input_value=input_value,
                system_message=system_message,
                temperature=temperature,
                top_p=top_p,
                model_name=body.model,
            ),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

    # ── Non-Streaming ────────────────────────────────────────────────────
    return _non_stream_response(
        model_url=model_url,
        model_id=model_id,
        api_key=api_key,
        input_value=input_value,
        system_message=system_message,
        temperature=temperature,
        top_p=top_p,
        model_name=body.model,
    )


# ── Non-Streaming handler ───────────────────────────────────────────────────

def _non_stream_response(
    model_url: str, model_id: str, api_key: str,
    input_value: str, system_message: str,
    temperature: float, top_p: float, model_name: str,
) -> JSONResponse:
    """Call Company LLM and return OpenAI-format response."""
    try:
        text = gauss_client.call(
            model_url=model_url,
            model_id=model_id,
            api_key=api_key,
            input_value=input_value,
            system_message=system_message,
            temperature=temperature,
            top_p=top_p,
        )
    except httpx.ConnectError:
        return _error_json(502, "Failed to connect to upstream LLM")
    except httpx.TimeoutException:
        return _error_json(504, "Upstream LLM timeout")
    except httpx.HTTPStatusError as e:
        return _error_json(e.response.status_code,
                           f"Upstream LLM error: {e.response.status_code}")
    except RuntimeError as e:
        return _error_json(500, str(e))

    response = ChatCompletionResponse(
        id=_generate_id(),
        created=int(time.time()),
        model=model_name,
        choices=[Choice(message=ResponseMessage(content=text))],
        usage=Usage(),
    )
    return JSONResponse(content=response.model_dump())


# ── Streaming handler ────────────────────────────────────────────────────────

import httpx  # noqa: E402 — needed for exception types in _non_stream_response


async def _stream_generator(
    model_url: str, model_id: str, api_key: str,
    input_value: str, system_message: str,
    temperature: float, top_p: float, model_name: str,
):
    """Yield SSE lines translating Company LLM streaming to OpenAI format.

    Ref: API_CONTRACT.md section 2.3
      - First chunk: delta has role + content
      - Subsequent chunks: delta has content only
      - Final chunk: delta is empty, finish_reason is "stop"
      - End with data: [DONE]
    """
    completion_id = _generate_id()
    created = int(time.time())
    is_first = True

    try:
        for chunk_text in gauss_client.stream_call(
            model_url=model_url,
            model_id=model_id,
            api_key=api_key,
            input_value=input_value,
            system_message=system_message,
            temperature=temperature,
            top_p=top_p,
        ):
            if is_first:
                delta = DeltaMessage(role="assistant", content=chunk_text)
                is_first = False
            else:
                delta = DeltaMessage(content=chunk_text)

            chunk = ChatCompletionChunk(
                id=completion_id,
                created=created,
                model=model_name,
                choices=[StreamChoice(delta=delta)],
            )
            yield f"data: {json.dumps(chunk.model_dump())}\n\n"

        # ── Final stop chunk ─────────────────────────────────────────────
        stop_chunk = ChatCompletionChunk(
            id=completion_id,
            created=created,
            model=model_name,
            choices=[StreamChoice(delta=DeltaMessage(), finish_reason="stop")],
        )
        yield f"data: {json.dumps(stop_chunk.model_dump())}\n\n"
        yield "data: [DONE]\n\n"

    except Exception as e:
        logger.error(f"Streaming error: {e}")
        error_chunk = ChatCompletionChunk(
            id=completion_id,
            created=created,
            model=model_name,
            choices=[StreamChoice(delta=DeltaMessage(), finish_reason="error")],
        )
        yield f"data: {json.dumps(error_chunk.model_dump())}\n\n"
        yield "data: [DONE]\n\n"


# ── Entrypoint ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=PROXY_HOST, port=PROXY_PORT)
