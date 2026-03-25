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
COMPANY_MODELS = {
    "Gauss2.3": {
        "model-id": "model-id",
        "model-url": "https://mycompany.com/api/v1/run/session_id",
    },
    "Gauss2.3 Think": {
        "model-id": "model-id",
        "model-url": "https://mycompany.com/api/v1/run/session_id",
    },
    "GaussO Flash": {
        "model-id": "model-id",
        "model-url": "https://mycompany.com/api/v1/run/session_id",
    },
    "GaussO Flash (S)": {
        "model-id": "model-id",
        "model-url": "https://mycompany.com/api/v1/run/session_id",
    },
    "GaussO4": {
        "model-id": "model-id",
        "model-url": "https://mycompany.com/api/v1/run/session_id",
    },
    "GaussO4 Thinking": {
        "model-id": "model-id",
        "model-url": "https://mycompany.com/api/v1/run/session_id",
    },
}


def get_model_config(model_name: str) -> dict:
    """Get model-id and model-url, with env override support.

    Priority:
      1. COMPANY_LLM_MODEL_ID + COMPANY_LLM_MODEL_URL env vars (override all)
      2. COMPANY_MODELS registry lookup
    """
    if COMPANY_LLM_MODEL_ID and COMPANY_LLM_MODEL_URL:
        return {"model-id": COMPANY_LLM_MODEL_ID, "model-url": COMPANY_LLM_MODEL_URL}
    if model_name not in COMPANY_MODELS:
        return None
    return COMPANY_MODELS[model_name]
