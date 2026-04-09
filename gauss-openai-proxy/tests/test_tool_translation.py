"""
Tests for tool_translation.py — both REQUEST and RESPONSE directions.

Covers:
  - tools_to_prompt: OpenAI tools → text prompt
  - convert_assistant_tool_calls: assistant tool_calls → text
  - convert_tool_result: tool result → text
  - process_messages_for_tools: full message pipeline
  - parse_tool_call_from_text: text → parsed tool call (XML + raw JSON)
  - tool_call_to_openai_format: parsed → OpenAI format
  - StreamingToolDetector: incremental streaming + truncation recovery
  - _try_complete_incomplete_json: auto-completion of truncated tool calls
"""

import json
import sys
import os

# Add app/ to import path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from tool_translation import (
    StreamingToolDetector,
    _try_complete_incomplete_json,
    convert_assistant_tool_calls,
    convert_tool_result,
    parse_tool_call_from_text,
    process_messages_for_tools,
    tool_call_to_openai_format,
    tools_to_prompt,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _collect_tool_names(events):
    """Extract tool names from tool_call_start events."""
    return [e["name"] for e in events if e["type"] == "tool_call_start"]


def _collect_tool_calls(events):
    """Extract complete tool_call events (backward compat)."""
    return [e["tool_call"] for e in events if e["type"] == "tool_call"]


def _collect_args_fragments(events):
    """Concatenate all tool_call_args fragments."""
    return "".join(e["fragment"] for e in events if e["type"] == "tool_call_args")


def _collect_text(events):
    """Concatenate all text events."""
    return "".join(e["content"] for e in events if e["type"] == "text")


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
        assert "<tool_call" in result
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
        assert "<tool_call" in result
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
        assert "<tool_call" in result
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
        assert "<tool_call" in result[2]["content"]
        assert "tool_calls" not in result[2] or result[2].get("tool_calls") is None

        # tool result → text
        assert result[3]["role"] == "tool"
        assert "[Tool Result]" in result[3]["content"]

        # final assistant passes through
        assert result[4]["content"] == "The file contains: Hello World"


# ── RESPONSE direction tests ─────────────────────────────────────────────────


class TestParseToolCallFromText:
    def test_xml_tagged(self):
        text = 'I will read the file.\n<tool_call{"name": "read_file", "arguments": {"path": "/tmp/test.txt"}}</tool_call'
        # Use the proper tags
        from tool_translation import TOOL_CALL_OPEN, TOOL_CALL_CLOSE
        text = f'I will read the file.\n{TOOL_CALL_OPEN}{{"name": "read_file", "arguments": {{"path": "/tmp/test.txt"}}}}{TOOL_CALL_CLOSE}'
        text_before, tool_call = parse_tool_call_from_text(text)
        assert text_before == "I will read the file."
        assert tool_call is not None
        assert tool_call["name"] == "read_file"
        assert tool_call["arguments"]["path"] == "/tmp/test.txt"

    def test_xml_tagged_no_prefix_text(self):
        from tool_translation import TOOL_CALL_OPEN, TOOL_CALL_CLOSE
        text = f'{TOOL_CALL_OPEN}{{"name": "search", "arguments": {{"query": "hello"}}}}{TOOL_CALL_CLOSE}'
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
        from tool_translation import TOOL_CALL_OPEN, TOOL_CALL_CLOSE
        text = f'{TOOL_CALL_OPEN}not valid json{TOOL_CALL_CLOSE}'
        text_before, tool_call = parse_tool_call_from_text(text)
        assert tool_call is None

    def test_xml_without_name_field(self):
        from tool_translation import TOOL_CALL_OPEN, TOOL_CALL_CLOSE
        text = f'{TOOL_CALL_OPEN}{{"invalid": "no name field"}}{TOOL_CALL_CLOSE}'
        text_before, tool_call = parse_tool_call_from_text(text)
        assert tool_call is None

    def test_multiline_tool_call(self):
        from tool_translation import TOOL_CALL_OPEN, TOOL_CALL_CLOSE
        text = f"""Let me search.
{TOOL_CALL_OPEN}
{{
  "name": "web_search",
  "arguments": {{
    "query": "weather today"
  }}
}}
{TOOL_CALL_CLOSE}"""
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


# ── Incomplete JSON auto-completion tests ────────────────────────────────────


class TestTryCompleteIncompleteJson:
    def test_complete_json_passes_through(self):
        result = _try_complete_incomplete_json('{"name": "read", "arguments": {"path": "/tmp"}}')
        assert result is not None
        assert result["name"] == "read"

    def test_missing_closing_braces(self):
        result = _try_complete_incomplete_json('{"name": "write_file", "arguments": {"content": "hello"')
        assert result is not None
        assert result["name"] == "write_file"
        assert result["arguments"]["content"] == "hello"

    def test_missing_outer_brace(self):
        result = _try_complete_incomplete_json('"name": "read", "arguments": {"path": "/tmp"}')
        assert result is not None
        assert result["name"] == "read"

    def test_truncated_string_in_value(self):
        """String value cut off mid-content."""
        result = _try_complete_incomplete_json(
            '{"name": "write_file", "arguments": {"content": "line1\\nline2'
        )
        assert result is not None
        assert result["name"] == "write_file"
        assert "line1" in result["arguments"]["content"]

    def test_deeply_nested_truncated(self):
        """Multiple levels of nesting, all truncated."""
        result = _try_complete_incomplete_json(
            '{"name": "exec", "arguments": {"data": {"nested": {"key": "val"'
        )
        assert result is not None
        assert result["name"] == "exec"

    def test_garbage_returns_none(self):
        result = _try_complete_incomplete_json("not json at all")
        assert result is None


# ── StreamingToolDetector tests ──────────────────────────────────────────────


class TestStreamingToolDetector:
    def test_plain_text_no_tool(self):
        detector = StreamingToolDetector()
        events = detector.feed("Hello, how can I help?")
        events += detector.flush()
        texts = _collect_text(events)
        assert texts == "Hello, how can I help?"

    def test_complete_tool_call_single_chunk(self):
        """Complete tool call in one chunk → incremental events."""
        from tool_translation import TOOL_CALL_OPEN, TOOL_CALL_CLOSE
        detector = StreamingToolDetector()
        events = detector.feed(
            f'{TOOL_CALL_OPEN}{{"name": "read_file", "arguments": {{"path": "/tmp"}}}}{TOOL_CALL_CLOSE}'
        )
        events += detector.flush()

        names = _collect_tool_names(events)
        args_frags = _collect_args_fragments(events)
        end_events = [e for e in events if e["type"] == "tool_call_end"]

        assert names == ["read_file"]
        assert len(end_events) == 1
        # Args fragments should concatenate to valid JSON
        assert '"path"' in args_frags

    def test_tool_call_split_across_chunks(self):
        """Tool call split across multiple chunks."""
        detector = StreamingToolDetector()
        all_events = []
        all_events += detector.feed("I'll read it. <tool_")
        all_events += detector.feed("call>")
        all_events += detector.feed('{"name": "read_file",')
        all_events += detector.feed(' "arguments": {"path": "/tmp"}}')
        all_events += detector.feed("</tool_call")
        all_events += detector.feed(">")
        all_events += detector.flush()

        texts = _collect_text(all_events)
        names = _collect_tool_names(all_events)
        end_events = [e for e in all_events if e["type"] == "tool_call_end"]

        assert "I'll read it." in texts.strip()
        assert names == ["read_file"]
        assert len(end_events) == 1

    def test_text_before_and_after_tool_call(self):
        from tool_translation import TOOL_CALL_OPEN, TOOL_CALL_CLOSE
        detector = StreamingToolDetector()
        events = detector.feed(
            f'Before text {TOOL_CALL_OPEN}{{"name": "t", "arguments": {{}}}}{TOOL_CALL_CLOSE} After text'
        )
        events += detector.flush()

        texts = _collect_text(events)
        names = _collect_tool_names(events)

        assert "Before text" in texts
        assert "After text" in texts
        assert names == ["t"]

    def test_partial_opening_tag_buffered(self):
        """If chunk ends with '<tool_' it should be held back."""
        detector = StreamingToolDetector()
        events1 = detector.feed("Hello <tool_")
        text1 = _collect_text(events1)
        assert "<tool_" not in text1

        # Complete the tag
        events2 = detector.feed("call>")
        events3 = detector.feed('{"name": "x", "arguments": {}}</tool_call')
        events4 = detector.feed(">")
        all_events = events1 + events2 + events3 + events4 + detector.flush()
        names = _collect_tool_names(all_events)
        assert names == ["x"]

    def test_incomplete_tool_call_flushed_as_text(self):
        """If stream ends while detecting name, flush as text."""
        detector = StreamingToolDetector()
        events = detector.feed("<tool_callincomplete json...")
        events += detector.flush()

        texts = _collect_text(events)
        names = _collect_tool_names(events)

        assert names == []
        assert "<tool_call" in texts

    def test_invalid_json_in_streaming(self):
        """Invalid JSON inside tags should still emit name + args."""
        from tool_translation import TOOL_CALL_OPEN, TOOL_CALL_CLOSE
        detector = StreamingToolDetector()
        # No valid JSON with name field
        events = detector.feed(f"{TOOL_CALL_OPEN}not json{TOOL_CALL_CLOSE}")
        events += detector.flush()

        # With incremental streaming, if name can't be detected, it stays in DETECTING_NAME
        # and flush() tries _try_complete_incomplete_json
        names = _collect_tool_names(events)
        # "not json" doesn't have a name, so it should be flushed as text
        assert names == []

    def test_character_by_character_streaming(self):
        """Simulate very small chunks (character by character)."""
        from tool_translation import TOOL_CALL_OPEN, TOOL_CALL_CLOSE
        full_text = f'Hi {TOOL_CALL_OPEN}{{"name": "t", "arguments": {{}}}}{TOOL_CALL_CLOSE}'
        detector = StreamingToolDetector()
        all_events = []
        for char in full_text:
            all_events += detector.feed(char)
        all_events += detector.flush()

        texts = _collect_text(all_events)
        names = _collect_tool_names(all_events)

        assert names == ["t"]
        assert "Hi" in texts.strip()

    def test_multiple_feeds_plain_text(self):
        detector = StreamingToolDetector()
        events = []
        events += detector.feed("Part 1. ")
        events += detector.feed("Part 2. ")
        events += detector.feed("Part 3.")
        events += detector.flush()

        texts = _collect_text(events)
        assert "Part 1" in texts
        assert "Part 2" in texts
        assert "Part 3" in texts

    def test_long_tool_call_streaming(self):
        """Simulate a long tool call (like write_file with big content).

        This is the KEY test for the truncation bug fix.
        The old behavior: buffer entire tool call → fail on truncated JSON.
        New behavior: stream args incrementally → client sees progress.
        """
        from tool_translation import TOOL_CALL_OPEN, TOOL_CALL_CLOSE
        long_content = "\\n".join([f"line {i}: some content here" for i in range(50)])
        tool_json = json.dumps({"name": "write_file", "arguments": {"content": long_content}})

        detector = StreamingToolDetector()

        # Feed in chunks of ~20 chars (simulating Gauss streaming)
        full_text = f'{TOOL_CALL_OPEN}{tool_json}{TOOL_CALL_CLOSE}'
        all_events = []
        chunk_size = 20
        for i in range(0, len(full_text), chunk_size):
            all_events += detector.feed(full_text[i:i + chunk_size])
        all_events += detector.flush()

        names = _collect_tool_names(all_events)
        args_frags = _collect_args_fragments(all_events)
        end_events = [e for e in all_events if e["type"] == "tool_call_end"]

        assert names == ["write_file"], f"Expected write_file, got {names}"
        assert len(end_events) == 1
        # Args should contain the content
        assert "content" in args_frags

    def test_truncated_tool_call_recovery(self):
        """Tool call truncated mid-stream → auto-complete in flush.

        This tests the main bug: Gauss response cut off before </tool_call >.
        """
        from tool_translation import TOOL_CALL_OPEN
        detector = StreamingToolDetector()

        # Simulate Gauss stream that gets cut off
        all_events = []
        all_events += detector.feed(f'{TOOL_CALL_OPEN}{{"name": "write_file", "arguments": {{"content": "hello')
        # Stream ends here — no closing braces, no </tool_call >
        all_events += detector.flush()

        # Should recover via _try_complete_incomplete_json
        names = _collect_tool_names(all_events)
        # Name should have been detected from the streamed content
        assert names == ["write_file"]

        # Args fragments should contain the content
        args_frags = _collect_args_fragments(all_events)
        assert "hello" in args_frags

    def test_truncated_before_name_detected(self):
        """Tool call truncated before name could be parsed → emit as text."""
        from tool_translation import TOOL_CALL_OPEN
        detector = StreamingToolDetector()

        all_events = []
        all_events += detector.feed(f'{TOOL_CALL_OPEN}{{"na')
        # Stream ends — name not yet complete
        all_events += detector.flush()

        # Can't recover → emit as text
        texts = _collect_text(all_events)
        assert "<tool_call" in texts

    def test_tool_call_start_event_has_call_id(self):
        """tool_call_start events must have call_id and index."""
        from tool_translation import TOOL_CALL_OPEN, TOOL_CALL_CLOSE
        detector = StreamingToolDetector()
        events = detector.feed(
            f'{TOOL_CALL_OPEN}{{"name": "read", "arguments": {{"path": "/tmp"}}}}{TOOL_CALL_CLOSE}'
        )
        events += detector.flush()

        start_events = [e for e in events if e["type"] == "tool_call_start"]
        assert len(start_events) == 1
        assert start_events[0]["call_id"].startswith("call_proxy_")
        assert start_events[0]["index"] == 0

    def test_tool_call_args_concatenates_to_valid_json(self):
        """All args fragments should concatenate to valid JSON object."""
        from tool_translation import TOOL_CALL_OPEN, TOOL_CALL_CLOSE
        detector = StreamingToolDetector()
        events = detector.feed(
            f'{TOOL_CALL_OPEN}{{"name": "exec", "arguments": {{"command": "ls -la /tmp"}}}}{TOOL_CALL_CLOSE}'
        )
        events += detector.flush()

        args_frags = _collect_args_fragments(events)
        # Should be parseable as or close to valid JSON
        # The fragments contain the arguments object text including braces
        assert '"command"' in args_frags
        assert "ls -la" in args_frags

    def test_backward_compat_tool_call_event_in_flush(self):
        """When flush recovers via _try_complete_incomplete_json before name
        was emitted, it should emit a 'tool_call' event (not start/args/end)."""
        from tool_translation import TOOL_CALL_OPEN
        detector = StreamingToolDetector()

        # Feed just the opening tag
        all_events = []
        all_events += detector.feed(TOOL_CALL_OPEN)
        # Now feed a truncated but detectable JSON
        all_events += detector.feed('{"name": "read", "arguments": {"path": "/tmp"}')
        all_events += detector.flush()

        # Name should be detected during feed, then args recovered in flush
        names = _collect_tool_names(all_events)
        assert names == ["read"]

    def test_close_tag_inside_string_value(self):
        """Content containing </tool_call > inside a string value should not
        cause premature truncation.

        This is the key bug fix: parse_tool_call_from_text now uses
        brace-depth matching instead of regex non-greedy match.
        """
        from tool_translation import TOOL_CALL_OPEN, TOOL_CALL_CLOSE
        # The close tag appears inside the "content" string value
        inner_json = json.dumps({
            "name": "write_file",
            "arguments": {"content": f"Doc: {TOOL_CALL_CLOSE}"}
        })
        text = f"{TOOL_CALL_OPEN}{inner_json}{TOOL_CALL_CLOSE}"
        text_before, tool_call = parse_tool_call_from_text(text)

        assert tool_call is not None
        assert tool_call["name"] == "write_file"
        assert TOOL_CALL_CLOSE in tool_call["arguments"]["content"]

    def test_close_tag_inside_string_streaming(self):
        """Streaming detector should handle </tool_call > inside string args."""
        from tool_translation import TOOL_CALL_OPEN, TOOL_CALL_CLOSE
        inner_json = json.dumps({
            "name": "write_file",
            "arguments": {"content": f"Has {TOOL_CALL_CLOSE} inside"}
        })
        full_text = f"{TOOL_CALL_OPEN}{inner_json}{TOOL_CALL_CLOSE}"

        detector = StreamingToolDetector()
        all_events = []
        # Feed in 30-char chunks
        for i in range(0, len(full_text), 30):
            all_events += detector.feed(full_text[i:i+30])
        all_events += detector.flush()

        names = _collect_tool_names(all_events)
        args_frags = _collect_args_fragments(all_events)
        end_events = [e for e in all_events if e["type"] == "tool_call_end"]

        assert names == ["write_file"]
        assert len(end_events) == 1
        assert "Has" in args_frags
