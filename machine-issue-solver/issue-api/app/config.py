"""
Configuration for Issue API
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Database
DB_PATH = os.getenv("DB_PATH", str(Path(__file__).parent.parent / "database" / "issues.db"))
DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"

# API Server
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8888"))
