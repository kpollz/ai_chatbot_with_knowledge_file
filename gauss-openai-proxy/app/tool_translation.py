"""
Tool translation layer: OpenAI function calling ↔ text-based tool calling.

Gauss LLM only returns plain text. This module:
  1. REQUEST direction: converts OpenAI tools[] → text prompt; converts
     assistant tool_calls and tool-result messages → plain text in conversation
  2. RESPONSE direction: detects tool call tags in Gauss text → OpenAI tool_calls format

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
TOOL_CALL_PATTERN = re.compile(r"<tool_call\s*>(.*?)</tool_call\s*>", re.DOTALL)

# Alternative tag patterns the model might use
TOOL_CALL_ALT_PATTERNS = [
    re.compile(r"<function_call\s*>(.*?)</function_call\s*>", re.DOTALL),
    re.compile(r"<tool\s*>(.*?)</tool\s*>", re.DOTALL),
]

# Pattern 2: Raw JSON fallback (when model skips XML tags)
RAW_TOOL_CALL_PATTERN = re.compile(
    r'\{[^{}]*"name"\s*:\s*"[^"]+?"[^{}]*"arguments"\s*:\s*\{[^{}]*\}[^{}]*\}'
    r"|"
    r'\{[^{}]*"arguments"\s*:\s*\{[^{}]*\}[^{}]*"name"\s*:\s*"[^"]+?"[^{}]*\}',
    re.DOTALL,
)

# Tags used for system prompt injection and streaming fallback text
TOOL_CALL_OPEN = "<tool_call" + ">"
TOOL_CALL_CLOSE = "</tool_call" + ">"

# Regex for streaming detection (flexible whitespace)
TOOL_CALL_OPEN_RE = re.compile(r"<tool_call\s*>")
TOOL_CALL_CLOSE_RE = re.compile(r"</tool_call\s*>")

# Prefixes for partial tag detection in streaming
_STREAMING_OPEN_PREFIX = "<tool_call"
_STREAMING_CLOSE_PREFIX = "</tool_call"


# ── JSON extraction helpers ──────────────────────────────────────────────────


def _clean_tool_call_content(text: str) -> str:
    """Clean content between tool call tags for JSON parsing.

    Handles common LLM output issues:
    - Markdown code blocks (```json ... ```)
    - Leading/trailing whitespace and newlines
    - BOM characters
    """
    text = text.strip()

    # Remove BOM if present
    if text.startswith("\ufeff"):
        text = text[1:].strip()

    # Strip markdown code block if present
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    return text


def _extract_json_tool_call(text: str) -> dict | None:
    """Extract a tool call JSON object from text using balanced brace matching.

    Robust against:
    - Nested arguments objects
    - Markdown wrappers around JSON
    - Extra text before/after the JSON object
    - Multi-line JSON with whitespace

    Returns parsed tool call dict {"name": ..., "arguments": {...}}, or None.
    """
    # First, try to clean and parse directly
    cleaned = _clean_tool_call_content(text)
    try:
        obj = json.loads(cleaned)
        if isinstance(obj, dict) and "name" in obj and "arguments" in obj:
            return obj
    except (json.JSONDecodeError, ValueError):
        pass

    # Balanced brace matching to find JSON objects with name + arguments
    i = 0
    while i < len(text):
        if text[i] != "{":
            i += 1
            continue

        # Found '{', try to find matching '}'
        depth = 0
        in_string = False
        escape_next = False

        for j in range(i, len(text)):
            c = text[j]

            if escape_next:
                escape_next = False
                continue
            if c == "\\" and in_string:
                escape_next = True
                continue
            if c == '"':
                in_string = not in_string
                continue
            if in_string:
                continue

            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[i : j + 1]
                    try:
                        obj = json.loads(candidate)
                        if (
                            isinstance(obj, dict)
                            and "name" in obj
                            and "arguments" in obj
                            and isinstance(obj.get("arguments"), (dict, type(None)))
                        ):
                            return obj
                    except (json.JSONDecodeError, ValueError):
                        pass
                    break

        i += 1

    return None


def _try_complete_incomplete_json(text: str) -> dict | None:
    """Try to parse incomplete tool call JSON by auto-completing it.

    Handles truncated Gauss responses where:
    - Closing braces are missing
    - String values are not closed
    - The tool call JSON is cut off mid-content
    - The outer { is missing entirely

    Returns parsed tool call dict, or None.
    """
    # First try normal extraction
    result = _extract_json_tool_call(text)
    if result:
        return result

    # Try wrapping in braces (handles missing outer brace)
    wrapped = "{" + text + "}"
    result = _extract_json_tool_call(wrapped)
    if result:
        return result

    # Analyze brace depth and string state
    depth = 0
    in_string = False
    escape_next = False

    for c in text:
        if escape_next:
            escape_next = False
            continue
        if in_string:
            if c == "\\":
                escape_next = True
            elif c == '"':
                in_string = False
        else:
            if c == '"':
                in_string = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1

    # Build completed text
    completed = text

    # Close open string first
    if in_string:
        completed += '"'

    # Close open braces (depth > 0 means unclosed braces)
    if depth > 0:
        completed += "}" * depth

    return _extract_json_tool_call(completed)


# ── REQUEST direction: tools → text ──────────────────────────────────────────


def tools_to_prompt(tools: list[dict]) -> str:
    """Convert OpenAI tool definitions to a text prompt.

    Appended to the end of the system message so the LLM knows
    how to call tools using <tool_call > syntax.

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
        f'{TOOL_CALL_OPEN}{{"name": "<tool_name>", "arguments": {{<args>}}}}{TOOL_CALL_CLOSE}',
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

    lines.extend(
        [
            "### Rules:",
            "- Call only ONE tool per response",
            f"- If you don't need a tool, respond directly without {TOOL_CALL_OPEN} tags",
            "- After receiving tool results, use that data to answer the user",
            "- Always include the tool name and all required arguments",
            "",
            "### IMPORTANT:",
            f"When you need to use a tool, output the {TOOL_CALL_OPEN} IMMEDIATELY "
            "without any explanatory text before it.",
            "Do NOT write sentences like 'I will check that' or 'Let me look that up' "
            "before the tool call.",
            f"Start your response directly with the {TOOL_CALL_OPEN} tag.",
        ]
    )

    return "\n".join(lines)


def convert_assistant_tool_calls(msg: dict) -> str:
    """Convert assistant message with tool_calls to plain text.

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
            func = getattr(tc, "function", {})
            name = func.get("name", "") if isinstance(func, dict) else getattr(func, "name", "")
            raw_args = func.get("arguments", "{}") if isinstance(func, dict) else getattr(func, "arguments", "{}")

        if isinstance(raw_args, str):
            try:
                args = json.loads(raw_args)
            except json.JSONDecodeError:
                args = {}
        else:
            args = raw_args

        tool_call_obj = {"name": name, "arguments": args}
        tool_call_text = json.dumps(tool_call_obj, ensure_ascii=False)
        text += f"\n{TOOL_CALL_OPEN}{tool_call_text}{TOOL_CALL_CLOSE}"

    return text.strip()


def convert_tool_result(msg: dict) -> str:
    """Convert tool result message to plain text.

    Ref: API_CONTRACT.md section 5.3
    """
    content = msg.get("content", "") or ""
    return f"[Tool Result]\n{content}\n[/Tool Result]"


def process_messages_for_tools(messages: list[dict]) -> list[dict]:
    """Process all messages: convert tool-related messages to plain text."""
    processed: list[dict] = []

    for msg in messages:
        role = msg.get("role", "")

        if role == "assistant" and msg.get("tool_calls"):
            processed.append(
                {
                    "role": "assistant",
                    "content": convert_assistant_tool_calls(msg),
                }
            )
        elif role == "tool":
            processed.append(
                {
                    "role": "tool",
                    "content": convert_tool_result(msg),
                }
            )
        else:
            processed.append(msg)

    return processed


# ── RESPONSE direction: text → tool_calls ────────────────────────────────────


def generate_tool_call_id() -> str:
    """Generate a unique tool call ID for proxy-created tool calls."""
    return f"call_proxy_{uuid.uuid4().hex[:8]}"


def parse_tool_call_from_text(text: str) -> tuple[str, dict | None]:
    """Parse tool call from complete Gauss response text.

    Ref: API_CONTRACT.md section 5.4

    Uses brace-depth matching to find the correct closing tag,
    robust against </tool_call > appearing inside string values.
    """
    # Try 1: Primary XML-tagged — use brace-depth matching for robustness
    open_match = TOOL_CALL_OPEN_RE.search(text)
    if open_match:
        content_start = open_match.end()
        # Find the correct closing tag by ensuring the JSON between them is balanced
        # This handles cases where </tool_call > appears inside string values
        close_pos = _find_close_tag_after_balanced_json(text, content_start)
        if close_pos is not None:
            inner = text[content_start:close_pos]
            tool_call = _extract_json_tool_call(inner)
            if tool_call:
                text_before = text[:open_match.start()].strip()
                return text_before, tool_call
            logger.warning(f"Failed to parse tool call from tagged content: {inner[:200]}")

    # Try 1b: Alternative tag formats
    for alt_open, alt_close in [
        (re.compile(r"<function_call\s*>"), re.compile(r"</function_call\s*>")),
        (re.compile(r"<tool\s*>"), re.compile(r"</tool\s*>")),
    ]:
        alt_match = alt_open.search(text)
        if alt_match:
            inner_start = alt_match.end()
            close = alt_close.search(text, inner_start)
            if close:
                tool_call = _extract_json_tool_call(text[inner_start:close.start()])
                if tool_call:
                    text_before = text[:alt_match.start()].strip()
                    return text_before, tool_call

    # Try 2: Raw JSON fallback
    match = RAW_TOOL_CALL_PATTERN.search(text)
    if match:
        try:
            tool_call = json.loads(match.group(0))
            if isinstance(tool_call, dict) and "name" in tool_call and "arguments" in tool_call:
                text_before = text[: match.start()].strip()
                return text_before, tool_call
        except json.JSONDecodeError:
            pass

    # Try 3: Balanced brace extraction
    if '"name"' in text and '"arguments"' in text:
        tool_call = _extract_json_tool_call(text)
        if tool_call:
            try:
                tool_json = json.dumps(tool_call, ensure_ascii=False)
                json_pos = text.find(tool_json)
            except Exception:
                json_pos = -1
            text_before = text[:json_pos].strip() if json_pos > 0 else ""
            return text_before, tool_call

    return text, None


def _find_close_tag_after_balanced_json(text: str, start: int) -> int | None:
    """Find </tool_call > position after a brace-balanced JSON object.

    Scans forward from `start`, tracking brace depth and string state.
    Once braces return to depth 0, looks for the closing tag.
    This correctly handles </tool_call > appearing inside string values.

    Returns the start position of the closing tag content (i.e., where
    the inner text ends), or None if not found.
    """
    depth = 0
    in_string = False
    escape_next = False
    i = start

    while i < len(text):
        c = text[i]

        if escape_next:
            escape_next = False
            i += 1
            continue

        if in_string:
            if c == "\\":
                escape_next = True
            elif c == '"':
                in_string = False
            i += 1
            continue

        if c == '"':
            in_string = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                # JSON object appears balanced — look for closing tag after this
                rest = text[i + 1 :]
                close_match = TOOL_CALL_CLOSE_RE.search(rest)
                if close_match:
                    return i + 1 + close_match.start()
                return None
        i += 1

    # If we get here, braces didn't balance — fall back to first close tag
    close_match = TOOL_CALL_CLOSE_RE.search(text, start)
    return close_match.start() if close_match else None


def tool_call_to_openai_format(tool_call: dict, index: int = 0) -> dict:
    """Convert parsed tool call dict to OpenAI tool_calls format.

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


def _safe_end_for_prefix(buffer: str, prefix: str) -> int:
    """Find safe position to emit, holding back potential partial prefix."""
    safe_end = len(buffer)
    for i in range(1, len(prefix) + 1):
        if buffer.endswith(prefix[:i]):
            safe_end = len(buffer) - i
            break
    return safe_end


class StreamingToolDetector:
    """Detect and incrementally stream tool calls from Gauss response text.

    States:
      PASSTHROUGH       — forward text as content deltas, look for <tool_call >
      DETECTING_NAME    — accumulate until function name found
      STREAMING_ARGS    — stream arguments text as fragments
      CONSUMING_CLOSE   — args complete, consume remaining until </tool_call >

    Events:
      {"type": "text", "content": "..."}
      {"type": "tool_call_start", "name": "...", "call_id": "...", "index": N}
      {"type": "tool_call_args", "fragment": "..."}
      {"type": "tool_call_end"}
      {"type": "tool_call", "tool_call": {...}}  — backward compat for flush
    """

    _OPEN_TAG_RE = re.compile(r"<tool_call\s*>")
    _CLOSE_TAG_RE = re.compile(r"</tool_call\s*>")
    _NAME_RE = re.compile(r'"name"\s*:\s*"([^"]+)"')
    _ARGS_KEY_RE = re.compile(r'"arguments"\s*:\s*')

    def __init__(self) -> None:
        self.state = "PASSTHROUGH"
        self.buffer = ""
        self._tool_name = ""
        self._call_id = ""
        self._tool_index = 0
        self._args_depth = 0
        self._in_string = False
        self._escape_next = False
        self._name_emitted = False

    def feed(self, chunk: str) -> list[dict]:
        """Feed a text chunk, return list of events to emit."""
        events: list[dict] = []
        self.buffer += chunk

        max_iter = 30
        iteration = 0
        while self.buffer and iteration < max_iter:
            iteration += 1
            prev_state = self.state

            if self.state == "PASSTHROUGH":
                new_events = self._handle_passthrough()
            elif self.state == "DETECTING_NAME":
                new_events = self._handle_detecting_name()
            elif self.state == "STREAMING_ARGS":
                new_events = self._handle_streaming_args()
            elif self.state == "CONSUMING_CLOSE":
                new_events = self._handle_consuming_close()
            else:
                break

            events.extend(new_events)

            if not new_events and self.state == prev_state:
                break

        return events

    def _handle_passthrough(self) -> list[dict]:
        """PASSTHROUGH: look for <tool_call > opening tag."""
        events: list[dict] = []
        match = self._OPEN_TAG_RE.search(self.buffer)

        if not match:
            safe_end = _safe_end_for_prefix(self.buffer, _STREAMING_OPEN_PREFIX)
            if safe_end > 0:
                events.append({"type": "text", "content": self.buffer[:safe_end]})
                self.buffer = self.buffer[safe_end:]
            return events

        if match.start() > 0:
            events.append({"type": "text", "content": self.buffer[: match.start()]})

        self.buffer = self.buffer[match.end() :]
        self.state = "DETECTING_NAME"
        self._name_emitted = False
        self._args_depth = 0
        self._in_string = False
        self._escape_next = False
        return events

    def _handle_detecting_name(self) -> list[dict]:
        """DETECTING_NAME: find function name, then arguments key."""
        events: list[dict] = []

        if not self._name_emitted:
            name_match = self._NAME_RE.search(self.buffer)
            if not name_match:
                return []

            self._tool_name = name_match.group(1)
            self._call_id = generate_tool_call_id()
            events.append(
                {
                    "type": "tool_call_start",
                    "name": self._tool_name,
                    "call_id": self._call_id,
                    "index": self._tool_index,
                }
            )
            self._name_emitted = True

        # Look for arguments key
        args_match = self._ARGS_KEY_RE.search(self.buffer)
        if not args_match:
            return events

        # Position after "arguments": and whitespace
        args_start = args_match.end()
        while args_start < len(self.buffer) and self.buffer[args_start] in " \t\n\r":
            args_start += 1

        if args_start >= len(self.buffer):
            self.buffer = ""
            self.state = "STREAMING_ARGS"
            return events

        self.buffer = self.buffer[args_start:]
        self.state = "STREAMING_ARGS"
        self._args_depth = 0
        self._in_string = False
        self._escape_next = False
        return events

    def _handle_streaming_args(self) -> list[dict]:
        """STREAMING_ARGS: stream arguments text as fragments.

        Uses brace depth tracking to detect when the arguments object ends.
        After args end, transitions to CONSUMING_CLOSE to eat remaining syntax.
        """
        events: list[dict] = []

        # Check if args end is within current buffer
        args_end_pos = self._find_args_end(self.buffer)

        if args_end_pos is not None:
            # Args object completed
            args_fragment = self.buffer[:args_end_pos]
            if args_fragment:
                events.append({"type": "tool_call_args", "fragment": args_fragment})

            # Remaining text after args (outer JSON braces, closing tag, etc.)
            self.buffer = self.buffer[args_end_pos:]
            events.append({"type": "tool_call_end"})
            self._tool_index += 1
            self.state = "CONSUMING_CLOSE"
            return events

        # Args not yet complete — emit safe portion as fragment
        # Hold back potential closing tag prefix + last 2 chars for braces
        safe_end = _safe_end_for_prefix(self.buffer, _STREAMING_CLOSE_PREFIX)
        if safe_end > 2:
            safe_end -= 2
        else:
            safe_end = 0

        if safe_end > 0:
            fragment = self.buffer[:safe_end]
            self.buffer = self.buffer[safe_end:]
            events.append({"type": "tool_call_args", "fragment": fragment})

        return events

    def _handle_consuming_close(self) -> list[dict]:
        """CONSUMING_CLOSE: discard everything until </tool_call >.

        After arguments end, there may be outer JSON closing braces, whitespace,
        and the closing tag. All of this should be silently consumed.
        """
        close_match = self._CLOSE_TAG_RE.search(self.buffer)
        if close_match:
            # Found closing tag — consume it and return to PASSTHROUGH
            self.buffer = self.buffer[close_match.end() :]
            self.state = "PASSTHROUGH"
            self._name_emitted = False
        else:
            # Closing tag not yet found — hold back potential partial prefix
            safe_end = _safe_end_for_prefix(self.buffer, _STREAMING_CLOSE_PREFIX)
            self.buffer = self.buffer[safe_end:]  # Discard consumed portion

        return []  # No events — everything here is discarded

    def _find_args_end(self, text: str) -> int | None:
        """Scan text to find where arguments object ends (brace depth → 0)."""
        depth = self._args_depth
        in_string = self._in_string
        escape_next = self._escape_next

        for i, c in enumerate(text):
            if escape_next:
                escape_next = False
                continue
            if in_string:
                if c == "\\":
                    escape_next = True
                elif c == '"':
                    in_string = False
            else:
                if c == '"':
                    in_string = True
                elif c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        self._args_depth = 0
                        self._in_string = False
                        self._escape_next = False
                        return i + 1

        self._args_depth = depth
        self._in_string = in_string
        self._escape_next = escape_next
        return None

    def flush(self) -> list[dict]:
        """Flush remaining buffer when stream ends."""
        events: list[dict] = []

        if not self.buffer:
            self.state = "PASSTHROUGH"
            return events

        if self.state == "DETECTING_NAME":
            tool_call = _try_complete_incomplete_json(self.buffer)
            if tool_call:
                logger.info(f"Recovered incomplete tool call in flush: {tool_call.get('name')}")
                events.append({"type": "tool_call", "tool_call": tool_call})
            else:
                events.append({"type": "text", "content": f"{TOOL_CALL_OPEN}{self.buffer}"})

        elif self.state == "STREAMING_ARGS":
            full_text = self.buffer
            tool_call_complete = _try_complete_incomplete_json(full_text)

            if tool_call_complete:
                logger.info(
                    f"Recovered truncated tool call in flush: {tool_call_complete.get('name')}"
                )
                if self._name_emitted:
                    args_obj = tool_call_complete.get("arguments", {})
                    args_str = json.dumps(args_obj, ensure_ascii=False)
                    events.append({"type": "tool_call_args", "fragment": args_str})
                    events.append({"type": "tool_call_end"})
                    self._tool_index += 1
                else:
                    events.append({"type": "tool_call", "tool_call": tool_call_complete})
            else:
                logger.warning(
                    f"Could not recover truncated tool call. Emitting {len(full_text)} chars as args"
                )
                if full_text:
                    events.append({"type": "tool_call_args", "fragment": full_text})
                if self._name_emitted:
                    events.append({"type": "tool_call_end"})
                    self._tool_index += 1
                else:
                    events = [{"type": "text", "content": f"{TOOL_CALL_OPEN}{full_text}"}]

        elif self.state == "CONSUMING_CLOSE":
            # Just discard remaining buffer (incomplete close tag, etc.)
            pass

        else:
            # PASSTHROUGH
            if '"name"' in self.buffer and '"arguments"' in self.buffer:
                tool_call = _extract_json_tool_call(self.buffer)
                if tool_call:
                    logger.info("Detected raw JSON tool call in stream flush")
                    events.append({"type": "tool_call", "tool_call": tool_call})
                    self.buffer = ""
                    self.state = "PASSTHROUGH"
                    return events

            events.append({"type": "text", "content": self.buffer})

        self.buffer = ""
        self.state = "PASSTHROUGH"
        return events