"""
Message normalization for OpenClaw → Gauss translation.

Handles:
  - content: array of content-parts → plain string
  - role: "developer" → "system"
  - flatten multi-turn messages → (system_message, input_value)

Ref: API_CONTRACT.md sections 4.1–4.3
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger("gauss-proxy")


# ── Content normalization ────────────────────────────────────────────────────


def normalize_content(content: Any) -> str:
    """Convert OpenAI content (string or content-parts array) to plain string.

    Handles:
      - str → pass through
      - list of content-parts → join text parts, skip image/other
      - None → ""
    """
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts: list[str] = []
        for item in content:
            if isinstance(item, str):
                texts.append(item)
            elif isinstance(item, dict):
                if item.get("type") == "text" and "text" in item:
                    texts.append(item["text"])
                # Skip image_url, image, and other non-text types
        return "\n".join(texts) if texts else ""
    return str(content)


# ── Role normalization ───────────────────────────────────────────────────────


def normalize_role(role: str) -> str:
    """Normalize role: developer → system, others pass through."""
    if role == "developer":
        return "system"
    return role


# ── Full message normalization ───────────────────────────────────────────────


def normalize_message(msg: dict) -> dict:
    """Normalize a single message: content + role.

    Does NOT handle tool translation — that's in tool_translation.py.
    """
    return {
        "role": normalize_role(msg.get("role", "user")),
        "content": normalize_content(msg.get("content")),
        # Pass through tool-related fields for tool_translation.py
        "tool_calls": msg.get("tool_calls"),
        "tool_call_id": msg.get("tool_call_id"),
    }


# ── Flatten messages → (system_message, input_value) ────────────────────────


def flatten_messages(messages: list[dict]) -> tuple[str, str]:
    """Flatten normalized messages into (input_value, system_message).

    Ref: API_CONTRACT.md section 4.3

    Rules:
      - system/developer role → system_message (last one wins)
      - Single user message → use directly as input_value
      - Multi-turn → formatted conversation with role prefixes
    """
    system_message = ""
    non_system: list[dict] = []

    for msg in messages:
        role = msg.get("role", "")
        if role == "system":
            system_message = msg.get("content", "")
        else:
            non_system.append(msg)

    if not non_system:
        return "", system_message

    # Single user message → use directly (no prefix needed)
    if len(non_system) == 1 and non_system[0].get("role") == "user":
        return non_system[0].get("content", ""), system_message

    # Multi-turn → formatted conversation
    role_map = {
        "user": "User",
        "assistant": "Assistant",
        "tool": "Tool Result",
    }
    parts: list[str] = []
    for msg in non_system:
        role = msg.get("role", "unknown")
        prefix = role_map.get(role, role.capitalize())
        content = msg.get("content", "")
        parts.append(f"{prefix}: {content}")

    return "\n".join(parts), system_message
