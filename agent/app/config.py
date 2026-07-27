"""
Configuration settings for Chatbot
"""

import os
from dotenv import load_dotenv

load_dotenv()

# Issue API (Sub-project 2)
ISSUE_API_URL = os.getenv("ISSUE_API_URL", "http://localhost:8888")

# LLM Configuration — OpenAI-compatible endpoint (native tool calling)
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0"))
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "")  # e.g. http://host:port/v1
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")    # may be overridden by the sidebar key
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "")        # model name sent to the endpoint

# Langfuse Configuration (optional - for tracing)
# Note: For langfuse v4, these env vars are read automatically by the SDK:
# - LANGFUSE_PUBLIC_KEY (or LANGFUSE_PK)
# - LANGFUSE_SECRET_KEY (or LANGFUSE_SK)  
# - LANGFUSE_HOST
# We keep them here for reference and backward compatibility
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "")
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

# Context Window
CONTEXT_WINDOW_LIMIT = int(os.getenv("CONTEXT_WINDOW_LIMIT", "128000"))
CONTEXT_WARN_THRESHOLD = int(os.getenv("CONTEXT_WARN_THRESHOLD", "100000"))
