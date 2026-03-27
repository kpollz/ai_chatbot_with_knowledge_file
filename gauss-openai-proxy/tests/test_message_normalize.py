"""Tests for message_normalize.py"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from message_normalize import flatten_messages, normalize_content, normalize_message, normalize_role


class TestNormalizeContent:
    def test_string_passthrough(self):
        assert normalize_content("hello") == "hello"

    def test_none_returns_empty(self):
        assert normalize_content(None) == ""

    def test_content_parts_array(self):
        content = [{"type": "text", "text": "Hello"}, {"type": "text", "text": "World"}]
        assert normalize_content(content) == "Hello\nWorld"

    def test_skip_image_parts(self):
        content = [
            {"type": "text", "text": "Look at this:"},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}},
        ]
        assert normalize_content(content) == "Look at this:"

    def test_string_items_in_list(self):
        content = ["hello", "world"]
        assert normalize_content(content) == "hello\nworld"

    def test_empty_list(self):
        assert normalize_content([]) == ""

    def test_non_string_non_list(self):
        assert normalize_content(42) == "42"


class TestNormalizeRole:
    def test_developer_to_system(self):
        assert normalize_role("developer") == "system"

    def test_user_passthrough(self):
        assert normalize_role("user") == "user"

    def test_assistant_passthrough(self):
        assert normalize_role("assistant") == "assistant"


class TestNormalizeMessage:
    def test_full_normalization(self):
        msg = {
            "role": "developer",
            "content": [{"type": "text", "text": "Be helpful"}],
        }
        result = normalize_message(msg)
        assert result["role"] == "system"
        assert result["content"] == "Be helpful"

    def test_tool_fields_preserved(self):
        msg = {
            "role": "assistant",
            "content": "text",
            "tool_calls": [{"id": "call_1"}],
            "tool_call_id": None,
        }
        result = normalize_message(msg)
        assert result["tool_calls"] == [{"id": "call_1"}]


class TestFlattenMessages:
    def test_single_user_message(self):
        messages = [{"role": "user", "content": "Hello"}]
        input_val, system = flatten_messages(messages)
        assert input_val == "Hello"
        assert system == ""

    def test_system_plus_user(self):
        messages = [
            {"role": "system", "content": "Be helpful"},
            {"role": "user", "content": "Hi"},
        ]
        input_val, system = flatten_messages(messages)
        assert input_val == "Hi"
        assert system == "Be helpful"

    def test_multi_turn(self):
        messages = [
            {"role": "system", "content": "System prompt"},
            {"role": "user", "content": "Question 1"},
            {"role": "assistant", "content": "Answer 1"},
            {"role": "user", "content": "Question 2"},
        ]
        input_val, system = flatten_messages(messages)
        assert system == "System prompt"
        assert "User: Question 1" in input_val
        assert "Assistant: Answer 1" in input_val
        assert "User: Question 2" in input_val

    def test_system_only(self):
        messages = [{"role": "system", "content": "Just system"}]
        input_val, system = flatten_messages(messages)
        assert input_val == ""
        assert system == "Just system"

    def test_last_system_wins(self):
        messages = [
            {"role": "system", "content": "First system"},
            {"role": "system", "content": "Second system"},
            {"role": "user", "content": "Hi"},
        ]
        _, system = flatten_messages(messages)
        assert system == "Second system"
