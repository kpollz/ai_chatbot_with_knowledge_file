"""Tests for schemas.py — validates Pydantic models accept OpenClaw formats."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from schemas import ChatCompletionRequest, ChatMessage, Tool, ToolFunction


class TestChatMessage:
    def test_string_content(self):
        msg = ChatMessage(role="user", content="Hello")
        assert msg.content == "Hello"

    def test_array_content(self):
        """OpenClaw sends content as array of content-parts."""
        msg = ChatMessage(
            role="user",
            content=[{"type": "text", "text": "Hello world"}],
        )
        assert isinstance(msg.content, list)
        assert msg.content[0]["text"] == "Hello world"

    def test_none_content(self):
        msg = ChatMessage(role="assistant", content=None)
        assert msg.content is None

    def test_extra_fields_ignored(self):
        """OpenClaw may send fields like 'name' or others we don't use."""
        msg = ChatMessage(role="user", content="Hi", name="test_user", unknown_field=True)
        assert msg.content == "Hi"

    def test_tool_fields(self):
        msg = ChatMessage(
            role="assistant",
            content="text",
            tool_calls=[{"id": "call_1", "function": {"name": "test"}}],
            tool_call_id=None,
        )
        assert msg.tool_calls is not None
        assert len(msg.tool_calls) == 1


class TestChatCompletionRequest:
    def test_minimal_request(self):
        req = ChatCompletionRequest(
            model="gauss-2.3",
            messages=[{"role": "user", "content": "Hello"}],
        )
        assert req.model == "gauss-2.3"
        assert len(req.messages) == 1

    def test_full_openclaw_request(self):
        """Simulates a realistic request from OpenClaw with all fields."""
        req = ChatCompletionRequest(
            model="gauss-2.3",
            messages=[
                {"role": "system", "content": "You are helpful"},
                {
                    "role": "user",
                    "content": [{"type": "text", "text": "What is 2+2?"}],
                },
            ],
            temperature=0.7,
            top_p=0.9,
            stream=True,
            max_completion_tokens=4096,
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "calculator",
                        "description": "Do math",
                        "parameters": {
                            "type": "object",
                            "properties": {"expression": {"type": "string"}},
                        },
                    },
                }
            ],
            tool_choice="auto",
            # Extra fields from OpenClaw that should be ignored:
            store=True,
            stream_options={"include_usage": True},
        )
        assert req.stream is True
        assert req.effective_max_tokens == 4096
        assert len(req.tools) == 1
        assert req.tools[0].function.name == "calculator"

    def test_effective_max_tokens_fallback(self):
        req = ChatCompletionRequest(
            model="gauss-2.3",
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=2048,
        )
        assert req.effective_max_tokens == 2048

    def test_effective_max_tokens_prefers_completion(self):
        req = ChatCompletionRequest(
            model="gauss-2.3",
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=1000,
            max_completion_tokens=4096,
        )
        assert req.effective_max_tokens == 4096


class TestTool:
    def test_basic_tool(self):
        tool = Tool(
            type="function",
            function=ToolFunction(
                name="read_file",
                description="Read a file",
                parameters={"type": "object", "properties": {"path": {"type": "string"}}},
            ),
        )
        assert tool.function.name == "read_file"
