"""
Configuration for Issue API (PostgreSQL)
"""

import os
from dotenv import load_dotenv

# Load .env but DO NOT override existing environment variables.
# This is important for Docker containers where env vars are set
# via docker-compose.yml and should take precedence over .env file.
load_dotenv(override=False)

# Database - PostgreSQL with asyncpg
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql+asyncpg://postgres:postgres@localhost:5432/issue_api"
)

# API Server
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8888"))
