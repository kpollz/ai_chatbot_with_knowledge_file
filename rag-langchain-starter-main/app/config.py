"""
Configuration settings for the RAG application.

Environment Variables:
- LLM_PROVIDER: LLM provider to use ("openai", "gemini", "ollama", "custom")
- LLM_MODEL: Model name (provider-specific)
- LLM_TEMPERATURE: Sampling temperature (default: 0)

Provider-specific API keys:
- OPENAI_API_KEY: For OpenAI/ChatGPT
- GOOGLE_API_KEY: For Google Gemini
- CUSTOM_LLM_API_KEY: For custom company LLM
- CUSTOM_LLM_BASE_URL: Base URL for custom company LLM (OpenAI-compatible)
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ---- LLM Configuration ----
# Default to Gemini as the LLM provider
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini")
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-1.5-flash")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0"))

# ---- API Keys (provider-specific) ----
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
CUSTOM_LLM_API_KEY = os.getenv("CUSTOM_LLM_API_KEY")
CUSTOM_LLM_BASE_URL = os.getenv("CUSTOM_LLM_BASE_URL")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# ---- Embedding Configuration ----
EMBED_MODEL = os.getenv("EMBED_MODEL", "all-MiniLM-L6-v2")

# ---- Vector Store Configuration ----
VECTOR_STORE_PROVIDER = os.getenv("VECTOR_STORE_PROVIDER", "chroma")  # "faiss" or "chroma"
PERSIST_DIR = os.getenv("PERSIST_DIR", "./index/faiss")
DATA_DIR = os.getenv("DATA_DIR", "./data/raw")
TOP_K = int(os.getenv("TOP_K", "4"))