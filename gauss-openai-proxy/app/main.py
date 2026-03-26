"""
Gauss OpenAI-Compatible Proxy — FastAPI Server

Translates between OpenAI Chat Completions API and Company LLM (Gauss) API.
Includes tool translation: OpenAI function calling ↔ text-based <tool_call>.

See API_CONTRACT.md for full schema and pipeline details.
"""

import json
import logging
import time
import uuid

import httpx
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
    TOOL_CALL_ENABLED,
    get_model_config,
)
from message_normalize import flatten_messages, normalize_content, normalize_message
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
from tool_translation import (
    StreamingToolDetector,
    parse_tool_call_from_text,
    process_messages_for_tools,
    tool_call_to_openai_format,
    tools_to_prompt,
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
    description="Translates OpenAI Chat Completions API to Company LLM (Gauss) API, "
    "with text-based tool calling emulation.",
    version="2.0.0",
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


def _error_json(
    status: int,
    message: str,
    error_type: str = "server_error",
    code: str | None = None,
) -> JSONResponse:
    """Return an OpenAI-format error response."""
    body = ErrorResponse(error=ErrorDetail(message=message, type=error_type, code=code))
    return JSONResponse(status_code=status, content=body.model_dump())


def _prepare_request(body: ChatCompletionRequest) -> tuple[str, str, list[dict]]:
    """Run the full request pipeline: normalize → tool translate → flatten.

    Returns: (input_value, system_message, tools_raw)
      - tools_raw: original tools list (for detecting if tools were sent)
    """
    # Step 1: Convert Pydantic messages to dicts
    raw_messages = []
    for msg in body.messages:
        raw_messages.append({
            "role": msg.role,
            "content": msg.content,
            "tool_calls": msg.tool_calls,
            "tool_call_id": msg.tool_call_id,
        })

    # Step 2: Normalize messages (content array→string, developer→system)
    normalized = [normalize_message(m) for m in raw_messages]

    # Step 3: Tool translation — convert tool-related messages to text
    if TOOL_CALL_ENABLED:
        processed = process_messages_for_tools(normalized)
    else:
        # Strip tool messages if tool translation disabled
        processed = [m for m in normalized if m.get("role") != "tool"]

    # Step 4: Inject tool prompt into system message
    tools_raw = []
    if TOOL_CALL_ENABLED and body.tools:
        tools_raw = [t.model_dump() for t in body.tools]
        tool_prompt = tools_to_prompt(tools_raw)
        if tool_prompt:
            _inject_tool_prompt(processed, tool_prompt)

    # Step 5: Flatten messages → (input_value, system_message)
    input_value, system_message = flatten_messages(processed)

    return input_value, system_message, tools_raw


def _inject_tool_prompt(messages: list[dict], tool_prompt: str) -> None:
    """Append tool_prompt to the system message in-place.

    If no system message exists, insert one at the beginning.
    """
    for msg in messages:
        if msg.get("role") == "system":
            msg["content"] = (msg.get("content", "") or "") + tool_prompt
            return

    # No system message found → insert one
    messages.insert(0, {"role": "system", "content": tool_prompt.lstrip("\n-")})


# ── Endpoints ────────────────────────────────────────────────────────────────


@app.get("/health")
async def health():
    return {"status": "ok", "version": "2.0.0", "tool_translation": TOOL_CALL_ENABLED}


@app.get("/v1/models")
async def list_models():
    now = int(time.time())
    data = [ModelObject(id=name, created=now) for name in COMPANY_MODELS]
    return ModelListResponse(data=data)


@app.post("/v1/chat/completions")
async def chat_completions(body: ChatCompletionRequest, request: Request):
    # ── Auth ─────────────────────────────────────────────────────────────
    api_key = _extract_api_key(request) or COMPANY_LLM_API_KEY
    if not api_key:
        return _error_json(
            401,
            "Missing API key. Provide Authorization: Bearer <key> header "
            "or set COMPANY_LLM_API_KEY env var.",
            error_type="authentication_error",
        )

    # ── Model lookup ─────────────────────────────────────────────────────
    model_config = get_model_config(body.model)
    if not model_config:
        return _error_json(
            404,
            f"Model not found: {body.model}",
            error_type="invalid_request_error",
            code="model_not_found",
        )

    # ── Prepare request (normalize + tool translate + flatten) ───────────
    input_value, system_message, tools_raw = _prepare_request(body)

    if not input_value and not system_message:
        return _error_json(
            400,
            "messages is required and must contain at least one non-system message",
            error_type="invalid_request_error",
        )

    # ── Parameters ───────────────────────────────────────────────────────
    temperature = body.temperature if body.temperature is not None else DEFAULT_TEMPERATURE
    top_p = body.top_p if body.top_p is not None else DEFAULT_TOP_P
    model_url = model_config["model-url"]
    model_id = model_config["model-id"]
    has_tools = TOOL_CALL_ENABLED and bool(tools_raw)

    logger.info(
        f"Request: model={body.model}, stream={body.stream}, "
        f"messages={len(body.messages)}, tools={len(tools_raw)}"
    )

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
                has_tools=has_tools,
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
        has_tools=has_tools,
    )


# ── Non-Streaming handler ───────────────────────────────────────────────────


def _non_stream_response(
    model_url: str,
    model_id: str,
    api_key: str,
    input_value: str,
    system_message: str,
    temperature: float,
    top_p: float,
    model_name: str,
    has_tools: bool,
) -> JSONResponse:
    """Call Company LLM and return OpenAI-format response.

    If has_tools is True, check response text for <tool_call> and convert.
    """
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
        return _error_json(e.response.status_code, f"Upstream LLM error: {e.response.status_code}")
    except RuntimeError as e:
        return _error_json(500, str(e))

    # ── Tool call detection (non-streaming) ──────────────────────────────
    if has_tools:
        text_before, tool_call = parse_tool_call_from_text(text)
        if tool_call:
            openai_tc = tool_call_to_openai_format(tool_call)
            response = ChatCompletionResponse(
                id=_generate_id(),
                created=int(time.time()),
                model=model_name,
                choices=[
                    Choice(
                        message=ResponseMessage(
                            content=text_before if text_before else None,
                            tool_calls=[openai_tc],
                        ),
                        finish_reason="tool_calls",
                    )
                ],
                usage=Usage(),
            )
            return JSONResponse(content=response.model_dump())

    # ── Normal text response ─────────────────────────────────────────────
    response = ChatCompletionResponse(
        id=_generate_id(),
        created=int(time.time()),
        model=model_name,
        choices=[Choice(message=ResponseMessage(content=text))],
        usage=Usage(),
    )
    return JSONResponse(content=response.model_dump())


# ── Streaming handler ────────────────────────────────────────────────────────


async def _stream_generator(
    model_url: str,
    model_id: str,
    api_key: str,
    input_value: str,
    system_message: str,
    temperature: float,
    top_p: float,
    model_name: str,
    has_tools: bool,
):
    """Yield SSE lines translating Company LLM streaming to OpenAI format.

    When has_tools is True, uses StreamingToolDetector to detect <tool_call>
    in the response and convert to SSE tool_calls format.

    Ref: API_CONTRACT.md sections 3.1, 3.2, 5.5
    """
    completion_id = _generate_id()
    created = int(time.time())
    is_first = True
    detected_tool_call = False
    detector = StreamingToolDetector() if has_tools else None

    def _make_chunk(delta: DeltaMessage, finish_reason: str | None = None) -> str:
        chunk = ChatCompletionChunk(
            id=completion_id,
            created=created,
            model=model_name,
            choices=[StreamChoice(delta=delta, finish_reason=finish_reason)],
        )
        return f"data: {json.dumps(chunk.model_dump())}\n\n"

    def _emit_text(text: str) -> str:
        """Create an SSE chunk for text content."""
        nonlocal is_first
        if is_first:
            is_first = False
            return _make_chunk(DeltaMessage(role="assistant", content=text))
        return _make_chunk(DeltaMessage(content=text))

    def _emit_tool_call(tool_call: dict) -> str:
        """Create an SSE chunk for a tool call."""
        nonlocal is_first, detected_tool_call
        detected_tool_call = True
        openai_tc = tool_call_to_openai_format(tool_call)
        if is_first:
            is_first = False
            return _make_chunk(DeltaMessage(role="assistant", tool_calls=[openai_tc]))
        return _make_chunk(DeltaMessage(tool_calls=[openai_tc]))

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
            if detector:
                # Tool-aware streaming: feed through detector
                events = detector.feed(chunk_text)
                for event in events:
                    if event["type"] == "text":
                        content = event["content"]
                        if content:
                            yield _emit_text(content)
                    elif event["type"] == "tool_call":
                        yield _emit_tool_call(event["tool_call"])
            else:
                # Simple streaming: no tool detection
                if is_first:
                    delta = DeltaMessage(role="assistant", content=chunk_text)
                    is_first = False
                else:
                    delta = DeltaMessage(content=chunk_text)
                yield _make_chunk(delta)

        # ── Flush remaining buffer ───────────────────────────────────────
        if detector:
            flush_events = detector.flush()
            for event in flush_events:
                if event["type"] == "text":
                    content = event["content"]
                    if content:
                        yield _emit_text(content)
                elif event["type"] == "tool_call":
                    yield _emit_tool_call(event["tool_call"])

        # ── Final stop chunk ─────────────────────────────────────────────
        finish_reason = "tool_calls" if detected_tool_call else "stop"
        yield _make_chunk(DeltaMessage(), finish_reason=finish_reason)
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
