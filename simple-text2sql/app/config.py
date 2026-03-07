"""Configuration for Simple Text2SQL"""

import os
from dotenv import load_dotenv

load_dotenv()

# LLM Configuration
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "company")
LLM_MODEL = os.getenv("LLM_MODEL", "Gauss2.3")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0"))

# Company LLM
COMPANY_LLM_API_KEY = os.getenv("COMPANY_LLM_API_KEY", "")
COMPANY_LLM_MODEL_ID = os.getenv("COMPANY_LLM_MODEL_ID")
COMPANY_LLM_MODEL_URL = os.getenv("COMPANY_LLM_MODEL_URL")

# Database
DB_PATH = os.getenv("DB_PATH", "./database/data.db")
SCHEMA_JSON_PATH = os.getenv("SCHEMA_JSON_PATH", "./database/schema.json")