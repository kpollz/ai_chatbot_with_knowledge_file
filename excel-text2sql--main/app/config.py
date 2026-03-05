"""
Configuration settings for Text2SQL Application
"""
import os
from dotenv import load_dotenv

load_dotenv()

# LLM Configuration
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini")
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-2.0-flash")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0"))

# API Keys
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Database Configuration
DB_PATH = os.getenv("DB_PATH", "./database/text2sql.db")
TABLE_NAME = os.getenv("TABLE_NAME", "excel_data")