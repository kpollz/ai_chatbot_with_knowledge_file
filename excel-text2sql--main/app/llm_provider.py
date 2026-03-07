"""
LLM Provider module for Text2SQL Application

Supports multiple LLM providers:
- gemini (default): Google's Gemini models
- openai: OpenAI's GPT models
- company: Company's proprietary LLM
"""

import os
import time
from typing import Optional
from config import LLM_PROVIDER, LLM_MODEL, LLM_TEMPERATURE, GOOGLE_API_KEY, OPENAI_API_KEY
from logger import logger, log_time


class LLMProvider:
    """Unified LLM provider for Text2SQL application."""
    
    def __init__(self, provider: Optional[str] = None, model: Optional[str] = None):
        self._provider = provider or LLM_PROVIDER
        self._model = model or LLM_MODEL
        self._llm = None
    
    def get_llm(self):
        """Get the configured LLM instance."""
        if self._llm is None:
            self._llm = self._create_llm()
        return self._llm
    
    def _create_llm(self):
        """Create the appropriate LLM based on provider."""
        provider = self._provider.lower()
        logger.info(f"Creating LLM: provider={provider}, model={self._model}")
        
        if provider == "gemini":
            return self._create_gemini_llm()
        elif provider == "openai":
            return self._create_openai_llm()
        elif provider == "company":
            return self._create_company_llm()
        else:
            raise ValueError(f"Unknown LLM provider: {provider}. Available: gemini, openai, company")
    
    def _create_gemini_llm(self):
        """Create a Gemini LLM instance."""
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError:
            raise ImportError("Install langchain-google-genai: pip install langchain-google-genai")
        
        api_key = GOOGLE_API_KEY or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("Set GOOGLE_API_KEY in your .env file")
        
        return ChatGoogleGenerativeAI(
            model=self._model,
            google_api_key=api_key,
            temperature=LLM_TEMPERATURE,
        )
    
    def _create_openai_llm(self):
        """Create an OpenAI LLM instance."""
        from langchain_openai import ChatOpenAI
        
        return ChatOpenAI(
            model=self._model,
            temperature=LLM_TEMPERATURE,
            api_key=OPENAI_API_KEY,
        )
    
    def _create_company_llm(self):
        """Create a Company LLM instance."""
        from company_chat_model import ChatCompanyLLM
        
        api_key = os.getenv("COMPANY_LLM_API_KEY")
        custom_model_id = os.getenv("COMPANY_LLM_MODEL_ID")
        custom_model_url = os.getenv("COMPANY_LLM_MODEL_URL")
        
        if not api_key:
            raise ValueError("Set COMPANY_LLM_API_KEY in your .env file")
        
        return ChatCompanyLLM(
            model=self._model,
            api_key=api_key,
            temperature=LLM_TEMPERATURE,
            custom_model_id=custom_model_id,
            custom_model_url=custom_model_url,
        )


def get_llm(provider: Optional[str] = None, model: Optional[str] = None):
    """Get an LLM instance."""
    return LLMProvider(provider, model).get_llm()