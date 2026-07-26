"""Server-only configuration.

The LLM / Issue API / Langfuse settings are NOT redefined here — they come from
the chatbot's ``config`` module, which this service reuses (same env var names).
This file only adds what a long-running server needs and Streamlit does not.

Named ``agent_config`` rather than ``config`` so it cannot shadow the reused
``chatbot/app/config.py`` on PYTHONPATH.
"""

import os

from dotenv import load_dotenv

load_dotenv(override=False)

# Where LangGraph persists conversation state (the checkpointer).
# Sync/psycopg URL — deliberately NOT the "+asyncpg" form the Issue API uses,
# because langgraph-checkpoint-postgres is built on psycopg.
CHECKPOINT_DATABASE_URL = os.getenv(
    "CHECKPOINT_DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/issue_api",
)

AGENT_HOST = os.getenv("AGENT_HOST", "0.0.0.0")
AGENT_PORT = int(os.getenv("AGENT_PORT", "8700"))

# Header each user's own LLM API key arrives in (BYOK — one key per user).
AGENT_API_KEY_HEADER = os.getenv("AGENT_API_KEY_HEADER", "x-openai-api-key")
