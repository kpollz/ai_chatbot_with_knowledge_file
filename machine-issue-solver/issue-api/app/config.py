"""
Configuration for Issue API (PostgreSQL)
"""

import os
from dotenv import load_dotenv

load_dotenv()

# Database - PostgreSQL with asyncpg
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql+asyncpg://postgres:postgres@localhost:5432/issue_api"
)

# API Server
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8888"))
