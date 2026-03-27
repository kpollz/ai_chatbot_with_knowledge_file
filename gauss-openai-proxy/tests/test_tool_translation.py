"""
Tests for tool_translation.py — both REQUEST and RESPONSE directions.

Covers:
  - tools_to_prompt: OpenAI tools → text prompt
  - convert_assistant_tool_calls: assistant tool_calls → text
  - convert_tool_result: tool result → text
  - process_messages_for_tools: full message pipeline
  - parse_tool_call_from_text: text → parsed tool call (XML + raw JSON)
  - tool_call_to_openai_format: parsed → OpenAI format
  - StreamingToolDetector: streaming state machine
"""

import json
import sys
import os

# Add app/ to import path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from tool_translation import (
    StreamingToolDetector,
    convert_assistant_tool_calls,
    convert_tool_result,
    parse_tool_call_from_text,
    process_messages_for_tools,
    tool_call_to_openai_format,
    tools_to_prompt,
)


# ── REQUEST direction tests ──────────────────────────────────────────────────


class TestToolsToPrompt:
    def test_empty_tools(self):
        assert tools_to_prompt([]) == ""

    def test_single_tool(self):
        tools = [
            {
                "function": {
                    "name": "read_file",
                    "description": "Read a file from disk",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "File path"},
                        },
                        "required": ["path"],
                    },
                }
            }
        ]
        result = tools_to_prompt(tools)
        assert "read_file" in result
        assert "Read a file from disk" in result
        assert "path" in result
        assert "<tool_call>" in result
        assert "required" in result

    def test_multiple_tools(self):
        tools = [
            {"function": {"name": "tool_a", "description": "Tool A"}},
            {"function": {"name": "tool_b", "description": "Tool B"}},
        ]
        result = tools_to_prompt(tools)
        assert "1. **tool_a**" in result
        assert "2. **tool_b**" in result


class TestConvertAssistantToolCalls:
    def test_with_tool_calls(self):
        msg = {
            "content": "Let me read that file.",
            "tool_calls": [
                {
                    "id": "call_abc",
                    "function": {
                        "name": "read_file",
                        "arguments": '{"path": "/tmp/test.txt"}',
                    },
                }
            ],
        }
        result = convert_assistant_tool_calls(msg)
        assert "Let me read that file." in result
        assert "<tool_call>" in result
        assert "read_file" in result
        assert "/tmp/test.txt" in result

    def test_without_tool_calls(self):
        msg = {"content": "Hello"}
        result = convert_assistant_tool_calls(msg)
        assert result == "Hello"

    def test_args_as_dict(self):
        msg = {
            "content": "",
            "tool_calls": [
                {
                    "function": {
                        "name": "search",
                        "arguments": {"query": "test"},  # dict, not string
                    }
                }
            ],
        }
        result = convert_assistant_tool_calls(msg)
        assert "<tool_call>" in result
        assert '"query": "test"' in result or '"query":"test"' in result


class TestConvertToolResult:
    def test_basic(self):
        msg = {"role": "tool", "tool_call_id": "call_abc", "content": "file contents here"}
        result = convert_tool_result(msg)
        assert result == "[Tool Result]\nfile contents here\n[/Tool Result]"

    def test_empty_content(self):
        msg = {"role": "tool", "content": ""}
        result = convert_tool_result(msg)
        assert "[Tool Result]" in result


class TestProcessMessagesForTools:
    def test_full_conversation(self):
        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Read /tmp/file.txt"},
            {
                "role": "assistant",
                "content": "I'll read that.",
                "tool_calls": [
                    {
                        "function": {
                            "name": "read_file",
                            "arguments": '{"path": "/tmp/file.txt"}',
                        }
                    }
                ],
            },
            {"role": "tool", "tool_call_id": "call_1", "content": "Hello World"},
            {"role": "assistant", "content": "The file contains: Hello World"},
        ]
        result = process_messages_for_tools(messages)

        # system and user pass through
        assert result[0]["role"] == "system"
        assert result[1]["role"] == "user"

        # assistant with tool_calls → text
        assert result[2]["role"] == "assistant"
        assert "<tool_call>" in result[2]["content"]
        assert "tool_calls" not in result[2] or result[2].get("tool_calls") is None

        # tool result → text
        assert result[3]["role"] == "tool"
        assert "[Tool Result]" in result[3]["content"]

        # final assistant passes through
        assert result[4]["content"] == "The file contains: Hello World"


# ── RESPONSE direction tests ─────────────────────────────────────────────────


class TestParseToolCallFromText:
    def test_xml_tagged(self):
        text = 'I will read the file.\n<tool_call>{"name": "read_file", "arguments": {"path": "/tmp/test.txt"}}</tool_call>'
        text_before, tool_call = parse_tool_call_from_text(text)
        assert text_before == "I will read the file."
        assert tool_call is not None
        assert tool_call["name"] == "read_file"
        assert tool_call["arguments"]["path"] == "/tmp/test.txt"

    def test_xml_tagged_no_prefix_text(self):
        text = '<tool_call>{"name": "search", "arguments": {"query": "hello"}}</tool_call>'
        text_before, tool_call = parse_tool_call_from_text(text)
        assert text_before == ""
        assert tool_call is not None
        assert tool_call["name"] == "search"

    def test_raw_json_fallback(self):
        text = 'Let me call this: {"name": "read_file", "arguments": {"path": "/tmp"}}'
        text_before, tool_call = parse_tool_call_from_text(text)
        assert tool_call is not None
        assert tool_call["name"] == "read_file"

    def test_no_tool_call(self):
        text = "This is just normal text with no tool calls."
        text_before, tool_call = parse_tool_call_from_text(text)
        assert text_before == text
        assert tool_call is None

    def test_invalid_json_in_xml(self):
        text = "<tool_call>not valid json</tool_call>"
        text_before, tool_call = parse_tool_call_from_text(text)
        # Falls through to raw JSON fallback, which also fails
        assert tool_call is None

    def test_xml_without_name_field(self):
        text = '<tool_call>{"invalid": "no name field"}</tool_call>'
        text_before, tool_call = parse_tool_call_from_text(text)
        assert tool_call is None

    def test_multiline_tool_call(self):
        text = """Let me search.
<tool_call>
{
  "name": "web_search",
  "arguments": {
    "query": "weather today"
  }
}
</tool_call>"""
        text_before, tool_call = parse_tool_call_from_text(text)
        assert tool_call is not None
        assert tool_call["name"] == "web_search"
        assert "weather today" in tool_call["arguments"]["query"]


class TestToolCallToOpenAIFormat:
    def test_basic(self):
        tool_call = {"name": "read_file", "arguments": {"path": "/tmp/test.txt"}}
        result = tool_call_to_openai_format(tool_call)
        assert result["type"] == "function"
        assert result["function"]["name"] == "read_file"
        assert result["index"] == 0
        assert result["id"].startswith("call_proxy_")
        # arguments should be a JSON string
        args = json.loads(result["function"]["arguments"])
        assert args["path"] == "/tmp/test.txt"

    def test_with_index(self):
        tool_call = {"name": "search", "arguments": {"query": "test"}}
        result = tool_call_to_openai_format(tool_call, index=2)
        assert result["index"] == 2

    def test_string_arguments(self):
        tool_call = {"name": "tool", "arguments": '{"key": "val"}'}
        result = tool_call_to_openai_format(tool_call)
        # Already a string, should be passed through
        assert result["function"]["arguments"] == '{"key": "val"}'


# ── StreamingToolDetector tests ──────────────────────────────────────────────


class TestStreamingToolDetector:
    def test_plain_text_no_tool(self):
        detector = StreamingToolDetector()
        events = detector.feed("Hello, how can I help?")
        events += detector.flush()
        texts = [e["content"] for e in events if e["type"] == "text"]
        assert "".join(texts) == "Hello, how can I help?"

    def test_complete_tool_call_single_chunk(self):
        detector = StreamingToolDetector()
        events = detector.feed(
            '<tool_call>{"name": "read_file", "arguments": {"path": "/tmp"}}</tool_call>'
        )
        events += detector.flush()
        tool_events = [e for e in events if e["type"] == "tool_call"]
        assert len(tool_events) == 1
        assert tool_events[0]["tool_call"]["name"] == "read_file"

    def test_tool_call_split_across_chunks(self):
        detector = StreamingToolDetector()
        all_events = []
        all_events += detector.feed("I'll read it. <tool_")
        all_events += detector.feed("call>")
        all_events += detector.feed('{"name": "read_file",')
        all_events += detector.feed(' "arguments": {"path": "/tmp"}}')
        all_events += detector.feed("</tool_call>")
        all_events += detector.flush()

        texts = [e["content"] for e in all_events if e["type"] == "text"]
        tool_events = [e for e in all_events if e["type"] == "tool_call"]

        assert "".join(texts).strip() == "I'll read it."
        assert len(tool_events) == 1
        assert tool_events[0]["tool_call"]["name"] == "read_file"

    def test_text_before_and_after_tool_call(self):
        detector = StreamingToolDetector()
        events = detector.feed(
            'Before text <tool_call>{"name": "t", "arguments": {}}</tool_call> After text'
        )
        events += detector.flush()

        texts = [e["content"] for e in events if e["type"] == "text"]
        tool_events = [e for e in events if e["type"] == "tool_call"]

        combined_text = "".join(texts)
        assert "Before text" in combined_text
        assert "After text" in combined_text
        assert len(tool_events) == 1

    def test_partial_opening_tag_buffered(self):
        """If chunk ends with '<tool_' it should be held back, not emitted."""
        detector = StreamingToolDetector()
        events1 = detector.feed("Hello <tool_")
        # The partial tag "<tool_" should be buffered
        text1 = "".join(e["content"] for e in events1 if e["type"] == "text")
        assert "<tool_" not in text1

        # Complete the tag
        events2 = detector.feed("call>")
        events3 = detector.feed('{"name": "x", "arguments": {}}</tool_call>')
        events4 = detector.flush()
        all_events = events1 + events2 + events3 + events4
        tool_events = [e for e in all_events if e["type"] == "tool_call"]
        assert len(tool_events) == 1

    def test_incomplete_tool_call_flushed_as_text(self):
        """If stream ends while buffering, flush as text."""
        detector = StreamingToolDetector()
        events = detector.feed("<tool_call>incomplete json...")
        events += detector.flush()

        texts = [e["content"] for e in events if e["type"] == "text"]
        tool_events = [e for e in events if e["type"] == "tool_call"]

        assert len(tool_events) == 0
        combined = "".join(texts)
        assert "<tool_call>" in combined
        assert "incomplete json..." in combined

    def test_invalid_json_in_streaming(self):
        """Invalid JSON inside tags should be emitted as text."""
        detector = StreamingToolDetector()
        events = detector.feed("<tool_call>not json</tool_call>")
        events += detector.flush()

        texts = [e["content"] for e in events if e["type"] == "text"]
        tool_events = [e for e in events if e["type"] == "tool_call"]

        assert len(tool_events) == 0
        combined = "".join(texts)
        assert "not json" in combined

    def test_character_by_character_streaming(self):
        """Simulate very small chunks (character by character)."""
        full_text = 'Hi <tool_call>{"name": "t", "arguments": {}}</tool_call>'
        detector = StreamingToolDetector()
        all_events = []
        for char in full_text:
            all_events += detector.feed(char)
        all_events += detector.flush()

        texts = [e["content"] for e in all_events if e["type"] == "text"]
        tool_events = [e for e in all_events if e["type"] == "tool_call"]

        assert len(tool_events) == 1
        assert tool_events[0]["tool_call"]["name"] == "t"
        combined_text = "".join(texts).strip()
        assert "Hi" in combined_text

    def test_multiple_feeds_plain_text(self):
        detector = StreamingToolDetector()
        events = []
        events += detector.feed("Part 1. ")
        events += detector.feed("Part 2. ")
        events += detector.feed("Part 3.")
        events += detector.flush()

        texts = [e["content"] for e in events if e["type"] == "text"]
        combined = "".join(texts)
        assert "Part 1" in combined
        assert "Part 2" in combined
        assert "Part 3" in combined
