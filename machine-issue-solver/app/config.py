"""
Configuration settings for Machine Issue Solver
"""

import os
from dotenv import load_dotenv

load_dotenv()

# LLM Configuration
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "company")
LLM_MODEL = os.getenv("LLM_MODEL", "Gauss2.3")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0"))

# Company LLM Configuration
COMPANY_LLM_API_KEY = os.getenv("COMPANY_LLM_API_KEY", "")
COMPANY_LLM_MODEL_ID = os.getenv("COMPANY_LLM_MODEL_ID")
COMPANY_LLM_MODEL_URL = os.getenv("COMPANY_LLM_MODEL_URL")

# Database Configuration
DB_PATH = os.getenv("DB_PATH", "./database/issues.db")

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