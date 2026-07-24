"""
Configuration settings for Chatbot
"""

import os
from dotenv import load_dotenv

load_dotenv()

# Issue API (Sub-project 2)
ISSUE_API_URL = os.getenv("ISSUE_API_URL", "http://localhost:8888")

# LLM Configuration
# Provider: "openai" (any OpenAI-compatible endpoint, native tool calling) | "company" (legacy Gauss)
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")
LLM_MODEL = os.getenv("LLM_MODEL", "Gauss2.3")  # used by the legacy "company" path
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0"))

# OpenAI-compatible endpoint (LLM_PROVIDER=openai)
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "")  # e.g. http://host:port/v1
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")    # may be overridden by the sidebar key
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "")        # model name sent to the endpoint

# Company LLM Configuration (legacy)
COMPANY_LLM_API_KEY = os.getenv("COMPANY_LLM_API_KEY", "")
COMPANY_LLM_MODEL_ID = os.getenv("COMPANY_LLM_MODEL_ID")
COMPANY_LLM_MODEL_URL = os.getenv("COMPANY_LLM_MODEL_URL")

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

# Available Company Models
COMPANY_MODELS = {
    "Gauss2.3": {
        "model-id": "model-id",
        "model-url": "https://mycompany.com/api/v1/run/session_id"
    },
    "Gauss2.3 Think": {
        "model-id": "model-id",
        "model-url": "https://mycompany.com/api/v1/run/session_id"
    },
    "GaussO Flash": {
        "model-id": "model-id",
        "model-url": "https://mycompany.com/api/v1/run/session_id"
    },
    "GaussO Flash (S)": {
        "model-id": "model-id",
        "model-url": "https://mycompany.com/api/v1/run/session_id"
    },
    "GaussO4": {
        "model-id": "model-id",
        "model-url": "https://mycompany.com/api/v1/run/session_id"
    },
    "GaussO4 Thinking": {
        "model-id": "model-id",
        "model-url": "https://mycompany.com/api/v1/run/session_id"
    },
}
