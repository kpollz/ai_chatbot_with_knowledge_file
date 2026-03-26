"""
Tool translation layer: OpenAI function calling ↔ text-based tool calling.

Gauss LLM only returns plain text. This module:
  1. REQUEST direction: converts OpenAI tools[] → text prompt; converts
     assistant tool_calls and tool-result messages → plain text in conversation
  2. RESPONSE direction: detects <tool_call> in Gauss text → OpenAI tool_calls format

Ref: API_CONTRACT.md section 5
Ref: machine-issue-solver/chatbot/app/graph.py — proven ReAct pattern
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Any

from message_normalize import normalize_content

logger = logging.getLogger("gauss-proxy")

# ── Detection patterns ───────────────────────────────────────────────────────

# Pattern 1: XML-tagged (recommended, most reliable)
TOOL_CALL_PATTERN = re.compile(r"<tool_call>(.*?)</tool_call>", re.DOTALL)

# Pattern 2: Raw JSON fallback (when model skips XML tags)
RAW_TOOL_CALL_PATTERN = re.compile(
    r'\{[^{}]*"name"\s*:\s*"[^"]+?"[^{}]*"arguments"\s*:\s*\{[^{}]*\}[^{}]*\}',
    re.DOTALL,
)

TOOL_CALL_OPEN = "<tool_call>"
TOOL_CALL_CLOSE = "</tool_call>"


# ── REQUEST direction: tools → text ──────────────────────────────────────────


def tools_to_prompt(tools: list[dict]) -> str:
    """Convert OpenAI tool definitions to a text prompt.

    Appended to the end of the system message so the LLM knows
    how to call tools using <tool_call> syntax.

    Ref: API_CONTRACT.md section 5.1
    """
    if not tools:
        return ""

    lines = [
        "",
        "---",
        "## Available Tools",
        "",
        "You have access to the following tools. "
        "To use a tool, include EXACTLY this syntax in your response:",
        '<tool_call>{"name": "<tool_name>", "arguments": {<args>}}</tool_call>',
        "",
        "### Tools:",
        "",
    ]

    for i, tool in enumerate(tools, 1):
        func = tool.get("function", tool)  # Handle both Tool and raw dict
        if isinstance(func, dict):
            name = func.get("name", "unknown")
            desc = func.get("description", "No description")
            params = func.get("parameters", {})
        else:
            # Pydantic ToolFunction object
            name = getattr(func, "name", "unknown")
            desc = getattr(func, "description", "No description") or "No description"
            params = getattr(func, "parameters", {}) or {}

        properties = params.get("properties", {}) if isinstance(params, dict) else {}
        required = set(params.get("required", [])) if isinstance(params, dict) else set()

        lines.append(f"{i}. **{name}** — {desc}")
        if properties:
            lines.append("   Parameters:")
            for prop_name, prop_schema in properties.items():
                prop_type = prop_schema.get("type", "any") if isinstance(prop_schema, dict) else "any"
                prop_desc = prop_schema.get("description", "") if isinstance(prop_schema, dict) else ""
                req_str = "required" if prop_name in required else "optional"
                desc_str = f": {prop_desc}" if prop_desc else ""
                lines.append(f"   - {prop_name} ({prop_type}, {req_str}){desc_str}")
        lines.append("")

    lines.extend([
        "### Rules:",
        "- Call only ONE tool per response",
        "- If you don't need a tool, respond directly without <tool_call> tags",
        "- After receiving tool results, use that data to answer the user",
        "- Always include the tool name and all required arguments",
    ])

    return "\n".join(lines)


def convert_assistant_tool_calls(msg: dict) -> str:
    """Convert assistant message with tool_calls to plain text.

    Input:
      content: "I'll read the file."
      tool_calls: [{id: "call_abc", function: {name: "read", arguments: '{"path": "/tmp"}'}}]

    Output:
      "I'll read the file.\n<tool_call>{\"name\": \"read\", \"arguments\": {\"path\": \"/tmp\"}}</tool_call>"

    Ref: API_CONTRACT.md section 5.2
    """
    text = msg.get("content", "") or ""

    tool_calls = msg.get("tool_calls")
    if not tool_calls:
        return text

    for tc in tool_calls:
        if isinstance(tc, dict):
            func = tc.get("function", {})
            name = func.get("name", "")
            raw_args = func.get("arguments", "{}")
        else:
            # Pydantic object fallback
            func = getattr(tc, "function", {})
            name = func.get("name", "") if isinstance(func, dict) else getattr(func, "name", "")
            raw_args = func.get("arguments", "{}") if isinstance(func, dict) else getattr(func, "arguments", "{}")

        # Parse arguments: could be JSON string or already a dict
        if isinstance(raw_args, str):
            try:
                args = json.loads(raw_args)
            except json.JSONDecodeError:
                args = {}
        else:
            args = raw_args

        tool_call_obj = {"name": name, "arguments": args}
        tool_call_text = json.dumps(tool_call_obj, ensure_ascii=False)
        text += f"\n<tool_call>{tool_call_text}</tool_call>"

    return text.strip()


def convert_tool_result(msg: dict) -> str:
    """Convert tool result message to plain text.

    Input:  {role: "tool", tool_call_id: "call_abc", content: "file contents..."}
    Output: "[Tool Result]\nfile contents...\n[/Tool Result]"

    Ref: API_CONTRACT.md section 5.3
    """
    content = msg.get("content", "") or ""
    return f"[Tool Result]\n{content}\n[/Tool Result]"


def process_messages_for_tools(messages: list[dict]) -> list[dict]:
    """Process all messages: convert tool-related messages to plain text.

    This runs AFTER message_normalize but BEFORE flatten_messages.

    - assistant with tool_calls → text with <tool_call> tags
    - tool result → text with [Tool Result] wrapper
    - system/user → pass through
    """
    processed: list[dict] = []

    for msg in messages:
        role = msg.get("role", "")

        if role == "assistant" and msg.get("tool_calls"):
            processed.append({
                "role": "assistant",
                "content": convert_assistant_tool_calls(msg),
            })
        elif role == "tool":
            processed.append({
                "role": "tool",
                "content": convert_tool_result(msg),
            })
        else:
            processed.append(msg)

    return processed


# ── RESPONSE direction: text → tool_calls ────────────────────────────────────


def generate_tool_call_id() -> str:
    """Generate a unique tool call ID for proxy-created tool calls."""
    return f"call_proxy_{uuid.uuid4().hex[:8]}"


def parse_tool_call_from_text(text: str) -> tuple[str, dict | None]:
    """Parse tool call from complete Gauss response text.

    Returns:
        (text_before_tool_call, parsed_tool_call_or_None)

    parsed_tool_call format:
        {"name": "read", "arguments": {"file_path": "/tmp/file.txt"}}

    Ref: API_CONTRACT.md section 5.4
    """
    # Try 1: XML-tagged
    match = TOOL_CALL_PATTERN.search(text)
    if match:
        try:
            tool_call = json.loads(match.group(1).strip())
            if isinstance(tool_call, dict) and "name" in tool_call:
                text_before = text[: match.start()].strip()
                return text_before, tool_call
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse tool call JSON: {match.group(1)[:200]}")

    # Try 2: Raw JSON fallback
    match = RAW_TOOL_CALL_PATTERN.search(text)
    if match:
        try:
            tool_call = json.loads(match.group(0))
            if isinstance(tool_call, dict) and "name" in tool_call:
                text_before = text[: match.start()].strip()
                logger.info("Detected raw JSON tool call (no XML tags)")
                return text_before, tool_call
        except json.JSONDecodeError:
            pass

    return text, None


def tool_call_to_openai_format(tool_call: dict, index: int = 0) -> dict:
    """Convert parsed tool call dict to OpenAI tool_calls format.

    Input:  {"name": "read", "arguments": {"file_path": "/tmp/file.txt"}}
    Output: {"index": 0, "id": "call_proxy_abc12345", "type": "function",
             "function": {"name": "read", "arguments": "{\"file_path\": ...}"}}

    Ref: API_CONTRACT.md section 5.6
    """
    call_id = generate_tool_call_id()
    arguments = tool_call.get("arguments", {})
    if isinstance(arguments, dict):
        arguments = json.dumps(arguments, ensure_ascii=False)

    return {
        "index": index,
        "id": call_id,
        "type": "function",
        "function": {
            "name": tool_call["name"],
            "arguments": arguments,
        },
    }


# ── Streaming tool call detection ────────────────────────────────────────────


class StreamingToolDetector:
    """Detect <tool_call>...</tool_call> in streaming text chunks.

    States:
      PASSTHROUGH — forward text as-is
      BUFFERING   — accumulating potential tool call content

    Ref: API_CONTRACT.md section 5.5
    """

    def __init__(self) -> None:
        self.state = "PASSTHROUGH"
        self.buffer = ""

    def feed(self, chunk: str) -> list[dict]:
        """Feed a text chunk, return list of events to emit.

        Event types:
          {"type": "text", "content": "..."}       — emit as SSE content delta
          {"type": "tool_call", "tool_call": {...}} — emit as SSE tool_calls delta
        """
        events: list[dict] = []
        self.buffer += chunk

        while self.buffer:
            if self.state == "PASSTHROUGH":
                tag_pos = self.buffer.find(TOOL_CALL_OPEN)

                if tag_pos == -1:
                    # No tag found. Hold back chars that could be a partial opening tag.
                    safe_end = len(self.buffer)
                    for i in range(1, len(TOOL_CALL_OPEN)):
                        if self.buffer.endswith(TOOL_CALL_OPEN[:i]):
                            safe_end = len(self.buffer) - i
                            break
                    if safe_end > 0:
                        events.append({"type": "text", "content": self.buffer[:safe_end]})
                    self.buffer = self.buffer[safe_end:]
                    break  # Need more data

                else:
                    # Found opening tag
                    if tag_pos > 0:
                        events.append({"type": "text", "content": self.buffer[:tag_pos]})
                    self.buffer = self.buffer[tag_pos + len(TOOL_CALL_OPEN) :]
                    self.state = "BUFFERING"

            elif self.state == "BUFFERING":
                close_pos = self.buffer.find(TOOL_CALL_CLOSE)

                if close_pos == -1:
                    break  # Need more data for closing tag

                # Found closing tag → parse tool call
                tool_json_str = self.buffer[:close_pos].strip()
                self.buffer = self.buffer[close_pos + len(TOOL_CALL_CLOSE) :]
                self.state = "PASSTHROUGH"

                try:
                    tool_call = json.loads(tool_json_str)
                    if isinstance(tool_call, dict) and "name" in tool_call:
                        events.append({"type": "tool_call", "tool_call": tool_call})
                    else:
                        # Invalid structure → emit as text
                        events.append({
                            "type": "text",
                            "content": f"<tool_call>{tool_json_str}</tool_call>",
                        })
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse streaming tool call: {tool_json_str[:200]}")
                    events.append({
                        "type": "text",
                        "content": f"<tool_call>{tool_json_str}</tool_call>",
                    })

        return events

    def flush(self) -> list[dict]:
        """Flush remaining buffer when stream ends."""
        events: list[dict] = []
        if self.buffer:
            if self.state == "BUFFERING":
                # Incomplete tool call → emit as plain text
                events.append({"type": "text", "content": f"<tool_call>{self.buffer}"})
            else:
                events.append({"type": "text", "content": self.buffer})
            self.buffer = ""
        self.state = "PASSTHROUGH"
        return events
