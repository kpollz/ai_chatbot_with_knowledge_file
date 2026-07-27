"""Environment configuration for the agent."""

import os
from dotenv import load_dotenv

load_dotenv()

# Issue API (Sub-project 2) — the only path to the database.
ISSUE_API_URL = os.getenv("ISSUE_API_URL", "http://localhost:8888")

# LLM — an OpenAI-compatible endpoint with native function calling.
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0"))
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "")  # e.g. http://host:port/v1
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "")        # model name sent to the endpoint

# Conversation threads. The checkpointer owns this database's schema, so it must
# not be the Issue API's.
DATABASE_URI = os.getenv(
    "DATABASE_URI", "postgresql://postgres:postgres@localhost:5432/agent_state"
)

# Langfuse (optional). The SDK reads these from the environment itself; they are
# mirrored here so is_configured() can tell whether tracing is on at all.
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "")
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
