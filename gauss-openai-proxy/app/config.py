"""
Configuration for Gauss OpenAI-Compatible Proxy

Model registry and env vars mirrored from:
  machine-issue-solver/chatbot/app/config.py
"""

import os
from dotenv import load_dotenv

load_dotenv()

# Proxy Server
PROXY_HOST = os.getenv("PROXY_HOST", "0.0.0.0")
PROXY_PORT = int(os.getenv("PROXY_PORT", "9000"))

# Company LLM Authentication
COMPANY_LLM_API_KEY = os.getenv("COMPANY_LLM_API_KEY", "")

# Override model-id / model-url for ALL models (same as machine-issue-solver)
COMPANY_LLM_MODEL_ID = os.getenv("COMPANY_LLM_MODEL_ID")
COMPANY_LLM_MODEL_URL = os.getenv("COMPANY_LLM_MODEL_URL")

# Defaults
DEFAULT_TEMPERATURE = float(os.getenv("DEFAULT_TEMPERATURE", "0"))
DEFAULT_TOP_P = float(os.getenv("DEFAULT_TOP_P", "0.95"))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "60"))
SSL_VERIFY = os.getenv("SSL_VERIFY", "false").lower() == "true"

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Model Registry — copied from machine-issue-solver/chatbot/app/config.py
# Replace placeholder values with real model-id and model-url
# Model Registry — copied from machine-issue-solver/chatbot/app/config.py
# Keys are slug-style IDs matching what OpenClaw sends in the "model" field.
# Replace placeholder model-id and model-url with real values.
COMPANY_MODELS = {
    "gauss-2.3": {
        "model-id": "model-id",
        "model-url": "https://mycompany.com/api/v1/run/session_id",
    },
    "gauss-2.3-think": {
        "model-id": "model-id",
        "model-url": "https://mycompany.com/api/v1/run/session_id",
    },
    "gausso-flash": {
        "model-id": "model-id",
        "model-url": "https://mycompany.com/api/v1/run/session_id",
    },
    "gausso-flash-s": {
        "model-id": "model-id",
        "model-url": "https://mycompany.com/api/v1/run/session_id",
    },
    "gausso4": {
        "model-id": "model-id",
        "model-url": "https://mycompany.com/api/v1/run/session_id",
    },
    "gausso4-thinking": {
        "model-id": "model-id",
        "model-url": "https://mycompany.com/api/v1/run/session_id",
    },
}

# Legacy name mapping — for backward compatibility with old callers
# that used the original display-style names (e.g. "Gauss2.3", "GaussO4")
_LEGACY_NAMES = {
    "Gauss2.3": "gauss-2.3",
    "Gauss2.3 Think": "gauss-2.3-think",
    "GaussO Flash": "gausso-flash",
    "GaussO Flash (S)": "gausso-flash-s",
    "GaussO4": "gausso4",
    "GaussO4 Thinking": "gausso4-thinking",
}


def get_model_config(model_name: str) -> dict:
    """Get model-id and model-url, with env override support.

    Priority:
      1. COMPANY_LLM_MODEL_ID + COMPANY_LLM_MODEL_URL env vars (override all)
      2. COMPANY_MODELS registry lookup (slug-style)
      3. _LEGACY_NAMES mapping (display-style → slug)
    """
    if COMPANY_LLM_MODEL_ID and COMPANY_LLM_MODEL_URL:
        return {"model-id": COMPANY_LLM_MODEL_ID, "model-url": COMPANY_LLM_MODEL_URL}
    if model_name in COMPANY_MODELS:
        return COMPANY_MODELS[model_name]
    slug = _LEGACY_NAMES.get(model_name)
    if slug and slug in COMPANY_MODELS:
        return COMPANY_MODELS[slug]
    return None
