"""
Integration tests for main.py — full request → response flow.

Uses unittest.mock to patch gauss_client calls so no real LLM is needed.
Tests:
  - Non-streaming text response
  - Non-streaming tool call response
  - Streaming text response
  - Streaming tool call response
  - Message normalization through the full pipeline
  - Error handling
"""

import json
import sys
import os
from unittest.mock import patch

import pytest

# Add app/ to import path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

# Must set env before importing main
os.environ.setdefault("COMPANY_LLM_API_KEY", "test-key")
os.environ.setdefault("TOOL_CALL_ENABLED", "true")

from fastapi.testclient import TestClient

from main import app


client = TestClient(app)


# ── Helpers ──────────────────────────────────────────────────────────────────

GAUSS_MODEL = "gauss-2.3"

SIMPLE_MESSAGES = [{"role": "user", "content": "Hello, how are you?"}]

CONTENT_ARRAY_MESSAGES = [
    {"role": "user", "content": [{"type": "text", "text": "What is 2+2?"}]}
]

TOOL_DEFS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "File path"}},
                "required": ["path"],
            },
        },
    }
]


def make_request(messages=None, stream=False, tools=None, **kwargs):
    body = {
        "model": GAUSS_MODEL,
        "messages": messages or SIMPLE_MESSAGES,
        "stream": stream,
    }
    if tools:
        body["tools"] = tools
    body.update(kwargs)
    return body


# ── Health endpoint ──────────────────────────────────────────────────────────


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


# ── Model listing ───────────────────────────────────────────────────────────


def test_list_models():
    resp = client.get("/v1/models")
    assert resp.status_code == 200
    data = resp.json()
    assert data["object"] == "list"
    model_ids = [m["id"] for m in data["data"]]
    assert "gauss-2.3" in model_ids


# ── Non-streaming: text response ────────────────────────────────────────────


@patch("main.gauss_client.call")
def test_non_streaming_text(mock_call):
    mock_call.return_value = "I'm doing great, thanks for asking!"

    resp = client.post(
        "/v1/chat/completions",
        json=make_request(),
        headers={"Authorization": "Bearer test-key"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["object"] == "chat.completion"
    assert data["choices"][0]["message"]["content"] == "I'm doing great, thanks for asking!"
    assert data["choices"][0]["finish_reason"] == "stop"
    mock_call.assert_called_once()


@patch("main.gauss_client.call")
def test_non_streaming_content_array(mock_call):
    """Content as array should be normalized before sending to Gauss."""
    mock_call.return_value = "4"

    resp = client.post(
        "/v1/chat/completions",
        json=make_request(messages=CONTENT_ARRAY_MESSAGES),
        headers={"Authorization": "Bearer test-key"},
    )
    assert resp.status_code == 200
    # Verify the call to gauss_client received normalized string
    call_kwargs = mock_call.call_args
    assert isinstance(call_kwargs.kwargs.get("input_value", call_kwargs[1].get("input_value", "")), str)


# ── Non-streaming: tool call response ───────────────────────────────────────


@patch("main.gauss_client.call")
def test_non_streaming_tool_call(mock_call):
    """When Gauss returns text with <tool_call>, proxy converts to OpenAI format."""
    mock_call.return_value = (
        'I\'ll read that file for you.\n'
        '<tool_call>{"name": "read_file", "arguments": {"path": "/tmp/test.txt"}}</tool_call>'
    )

    resp = client.post(
        "/v1/chat/completions",
        json=make_request(tools=TOOL_DEFS),
        headers={"Authorization": "Bearer test-key"},
    )
    assert resp.status_code == 200
    data = resp.json()
    choice = data["choices"][0]
    assert choice["finish_reason"] == "tool_calls"
    assert choice["message"]["tool_calls"] is not None
    assert len(choice["message"]["tool_calls"]) == 1

    tc = choice["message"]["tool_calls"][0]
    assert tc["type"] == "function"
    assert tc["function"]["name"] == "read_file"
    assert tc["id"].startswith("call_proxy_")

    args = json.loads(tc["function"]["arguments"])
    assert args["path"] == "/tmp/test.txt"

    # Text before tool call should be in content
    assert "read that file" in (choice["message"]["content"] or "")


@patch("main.gauss_client.call")
def test_non_streaming_no_tool_detection_without_tools(mock_call):
    """Without tools in request, <tool_call> in response should NOT be parsed."""
    mock_call.return_value = '<tool_call>{"name": "x", "arguments": {}}</tool_call>'

    resp = client.post(
        "/v1/chat/completions",
        json=make_request(tools=None),  # No tools!
        headers={"Authorization": "Bearer test-key"},
    )
    assert resp.status_code == 200
    data = resp.json()
    # Should be treated as plain text
    assert data["choices"][0]["finish_reason"] == "stop"
    assert "<tool_call>" in data["choices"][0]["message"]["content"]


# ── Streaming: text response ────────────────────────────────────────────────


@patch("main.gauss_client.stream_call")
def test_streaming_text(mock_stream):
    mock_stream.return_value = iter(["Hello", ", ", "world", "!"])

    resp = client.post(
        "/v1/chat/completions",
        json=make_request(stream=True),
        headers={"Authorization": "Bearer test-key"},
    )
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]

    lines = resp.text.strip().split("\n\n")
    data_lines = [l for l in lines if l.startswith("data: ") and l != "data: [DONE]"]

    # Should have content chunks
    assert len(data_lines) >= 1

    # First chunk should have role=assistant
    first = json.loads(data_lines[0].removeprefix("data: "))
    assert first["choices"][0]["delta"]["role"] == "assistant"

    # Last data line before [DONE] should have finish_reason
    last = json.loads(data_lines[-1].removeprefix("data: "))
    assert last["choices"][0]["finish_reason"] == "stop"


# ── Streaming: tool call response ───────────────────────────────────────────


@patch("main.gauss_client.stream_call")
def test_streaming_tool_call(mock_stream):
    """Streaming response with <tool_call> should emit tool_calls delta."""
    mock_stream.return_value = iter([
        "Let me ",
        "read it. ",
        "<tool_call>",
        '{"name": "read_file", ',
        '"arguments": {"path": "/tmp"}}',
        "</tool_call>",
    ])

    resp = client.post(
        "/v1/chat/completions",
        json=make_request(stream=True, tools=TOOL_DEFS),
        headers={"Authorization": "Bearer test-key"},
    )
    assert resp.status_code == 200

    lines = resp.text.strip().split("\n\n")
    data_lines = [l for l in lines if l.startswith("data: ") and l != "data: [DONE]"]

    # Collect all events
    text_content = []
    tool_call_found = False
    finish_reason = None

    for line in data_lines:
        chunk = json.loads(line.removeprefix("data: "))
        delta = chunk["choices"][0]["delta"]
        fr = chunk["choices"][0].get("finish_reason")

        if delta.get("content"):
            text_content.append(delta["content"])
        if delta.get("tool_calls"):
            tool_call_found = True
            tc = delta["tool_calls"][0]
            assert tc["function"]["name"] == "read_file"
        if fr:
            finish_reason = fr

    assert tool_call_found, "Expected a tool_calls delta event"
    assert finish_reason == "tool_calls"
    assert "read it" in "".join(text_content)


# ── Error handling ──────────────────────────────────────────────────────────


def test_unknown_model():
    resp = client.post(
        "/v1/chat/completions",
        json=make_request(messages=SIMPLE_MESSAGES),
        headers={"Authorization": "Bearer test-key"},
    )
    # gauss-2.3 exists, so test with a fake model
    body = make_request()
    body["model"] = "nonexistent-model"
    resp = client.post(
        "/v1/chat/completions",
        json=body,
        headers={"Authorization": "Bearer test-key"},
    )
    assert resp.status_code == 200  # JSONResponse with 404 inside
    data = resp.json()
    assert data["error"]["code"] == "model_not_found"


def test_extra_fields_accepted():
    """OpenClaw sends many extra fields; they should be silently ignored."""
    body = make_request()
    body.update({
        "store": True,
        "stream_options": {"include_usage": True},
        "frequency_penalty": 0,
        "presence_penalty": 0,
        "logprobs": False,
        "top_logprobs": None,
    })

    with patch("main.gauss_client.call", return_value="OK"):
        resp = client.post(
            "/v1/chat/completions",
            json=body,
            headers={"Authorization": "Bearer test-key"},
        )
    assert resp.status_code == 200


# ── Multi-turn with tool results ────────────────────────────────────────────


@patch("main.gauss_client.call")
def test_multi_turn_with_tool_results(mock_call):
    """Full conversation with tool call and tool result should work."""
    mock_call.return_value = "The file contains: Hello World"

    messages = [
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Read /tmp/test.txt"},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_abc",
                    "type": "function",
                    "function": {
                        "name": "read_file",
                        "arguments": '{"path": "/tmp/test.txt"}',
                    },
                }
            ],
        },
        {"role": "tool", "tool_call_id": "call_abc", "content": "Hello World"},
    ]

    resp = client.post(
        "/v1/chat/completions",
        json=make_request(messages=messages, tools=TOOL_DEFS),
        headers={"Authorization": "Bearer test-key"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["choices"][0]["message"]["content"] == "The file contains: Hello World"

    # Verify gauss_client received properly processed messages
    call_kwargs = mock_call.call_args
    input_value = call_kwargs.kwargs.get("input_value") or call_kwargs[1].get("input_value", "")
    system_message = call_kwargs.kwargs.get("system_message") or call_kwargs[1].get("system_message", "")

    # System message should contain tool prompt
    assert "read_file" in system_message
    # Input value should contain the conversation
    assert "Read /tmp/test.txt" in input_value
    assert "[Tool Result]" in input_value
    assert "Hello World" in input_value
