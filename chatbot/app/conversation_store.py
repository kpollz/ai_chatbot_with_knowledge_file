"""
JSON file storage for conversations and feedback

Each session is saved as a separate JSON file in the conversations/ directory.
Structure:
  {
    "session_id": "abc12345",
    "created_at": "2026-03-19T10:00:00",
    "updated_at": "2026-03-19T10:05:00",
    "message_count": 4,
    "messages": [
      {"role": "user", "content": "...", "timestamp": "...", "feedback": null},
      {"role": "assistant", "content": "...", "timestamp": "...", "feedback": "like"}
    ]
  }
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict

from logger import logger

CONVERSATIONS_DIR = Path(__file__).parent.parent / "conversations"


def _ensure_dir():
    CONVERSATIONS_DIR.mkdir(parents=True, exist_ok=True)


def create_session_id() -> str:
    """Create a new short session ID."""
    return uuid.uuid4().hex[:8]


def save_conversation(session_id: str, messages: List[Dict]) -> None:
    """Save or update conversation JSON file."""
    _ensure_dir()
    filepath = CONVERSATIONS_DIR / f"session_{session_id}.json"
    now = datetime.now().isoformat()

    # Preserve created_at from existing file
    created_at = now
    if filepath.exists():
        try:
            existing = json.loads(filepath.read_text(encoding="utf-8"))
            created_at = existing.get("created_at", now)
        except Exception:
            pass

    data = {
        "session_id": session_id,
        "created_at": created_at,
        "updated_at": now,
        "message_count": len(messages),
        "messages": messages,
    }

    filepath.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info(f"Saved conversation {session_id} ({len(messages)} messages)")
