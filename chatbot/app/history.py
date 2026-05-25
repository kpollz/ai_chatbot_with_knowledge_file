"""
Message history and context window management

Token estimation uses a character-based approximation:
- Vietnamese text: ~2-3 characters per token
- English text: ~4 characters per token
- We use ~3 chars/token as a conservative middle ground
"""

from typing import List, Dict, Tuple

from config import CONTEXT_WINDOW_LIMIT, CONTEXT_WARN_THRESHOLD
from logger import logger

CHARS_PER_TOKEN = 3  # Conservative estimate for mixed Vietnamese/English


def estimate_tokens(text: str) -> int:
    """Estimate token count from text length."""
    if not text:
        return 0
    return len(text) // CHARS_PER_TOKEN


def estimate_messages_tokens(messages: List[Dict[str, str]]) -> int:
    """Estimate total tokens across all messages in history."""
    total = 0
    for msg in messages:
        total += estimate_tokens(msg.get("content", ""))
        total += 4  # overhead per message (role, formatting)
    return total


def check_context_limit(messages: List[Dict[str, str]]) -> Tuple[str, int]:
    """
    Check if message history is approaching the context window limit.

    Returns:
        (status, estimated_tokens) where status is one of:
        - "ok": Under warning threshold
        - "warning": Between warning and hard limit
        - "exceeded": Over hard limit
    """
    tokens = estimate_messages_tokens(messages)

    if tokens >= CONTEXT_WINDOW_LIMIT:
        logger.warning(f"Context limit EXCEEDED: ~{tokens} tokens >= {CONTEXT_WINDOW_LIMIT}")
        return "exceeded", tokens
    elif tokens >= CONTEXT_WARN_THRESHOLD:
        logger.warning(f"Context limit WARNING: ~{tokens} tokens >= {CONTEXT_WARN_THRESHOLD}")
        return "warning", tokens
    else:
        return "ok", tokens


def format_history_for_prompt(messages: List[Dict[str, str]]) -> str:
    """
    Format message history as a string to include in the LLM prompt.
    Only includes user and assistant messages (skips system).
    """
    if not messages:
        return ""

    lines = []
    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role == "user":
            lines.append(f"User: {content}")
        elif role == "assistant":
            lines.append(f"Assistant: {content}")

    if not lines:
        return ""

    return "Lich su hoi thoai:\n" + "\n".join(lines)
