"""
LLM Provider Module - A wrapper for different LLM providers.

This module provides a unified interface for using different LLM providers
(OpenAI, Gemini, Ollama, or custom company LLMs).

To add your own company LLM:
1. Create a new class that inherits from BaseLLMProvider
2. Implement the `get_llm()` method to return your custom LLM instance
3. Add your provider to the LLMFactory.PROVIDERS dictionary
4. Set LLM_PROVIDER="your_provider_name" in your .env file
"""

from abc import ABC, abstractmethod
from typing import Optional
import os


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers.
    
    Inherit from this class to create your own custom LLM provider.
    You must implement the get_llm() method.
    """
    
    def __init__(self, model: str, temperature: float = 0, **kwargs):
        """
        Initialize the LLM provider.
        
        Args:
            model: The model name/identifier to use
            temperature: Sampling temperature (0 = deterministic, 1 = creative)
            **kwargs: Additional provider-specific arguments
        """
        self.model = model
        self.temperature = temperature
        self.kwargs = kwargs
    
    @abstractmethod
    def get_llm(self):
        """Return the LLM instance.
        
        Returns:
            A LangChain-compatible LLM instance
        """
        pass


class OpenAIProvider(BaseLLMProvider):
    """OpenAI LLM Provider (ChatGPT)."""
    
    def __init__(self, model: str = "gpt-4o-mini", temperature: float = 0, 
                 api_key: Optional[str] = None, **kwargs):
        super().__init__(model, temperature, **kwargs)
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY not set. Please set it in your .env file or pass it directly.")
    
    def get_llm(self):
        """Return a ChatOpenAI instance."""
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=self.model,
            temperature=self.temperature,
            api_key=self.api_key,
            **self.kwargs
        )


class GeminiProvider(BaseLLMProvider):
    """Google Gemini LLM Provider."""
    
    def __init__(self, model: str = "gemini-1.5-flash", temperature: float = 0,
                 api_key: Optional[str] = None, **kwargs):
        super().__init__(model, temperature, **kwargs)
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        
        if not self.api_key:
            raise RuntimeError("GOOGLE_API_KEY not set. Please set it in your .env file or pass it directly.")
    
    def get_llm(self):
        """Return a ChatGoogleGenerativeAI instance."""
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=self.model,
            temperature=self.temperature,
            google_api_key=self.api_key,
            **self.kwargs
        )


class OllamaProvider(BaseLLMProvider):
    """Ollama LLM Provider (local models)."""
    
    def __init__(self, model: str = "llama2", temperature: float = 0, 
                 base_url: Optional[str] = None, **kwargs):
        super().__init__(model, temperature, **kwargs)
        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    
    def get_llm(self):
        """Return a ChatOllama instance."""
        from langchain_community.chat_models import ChatOllama
        return ChatOllama(
            model=self.model,
            temperature=self.temperature,
            base_url=self.base_url,
            **self.kwargs
        )


class CustomLLMProvider(BaseLLMProvider):
    """
    Template for OpenAI-compatible custom LLM integration.
    
    Use this if your company's LLM has an OpenAI-compatible API endpoint.
    For company-specific API formats, use CompanyLLMProvider instead.
    """
    
    def __init__(self, model: str = "custom-model", temperature: float = 0,
                 api_key: Optional[str] = None, base_url: Optional[str] = None,
                 **kwargs):
        super().__init__(model, temperature, **kwargs)
        self.api_key = api_key or os.getenv("CUSTOM_LLM_API_KEY")
        self.base_url = base_url or os.getenv("CUSTOM_LLM_BASE_URL")
        
        if not self.api_key:
            raise RuntimeError("CUSTOM_LLM_API_KEY not set. Please set it in your .env file.")
        if not self.base_url:
            raise RuntimeError("CUSTOM_LLM_BASE_URL not set. Please set it in your .env file.")
    
    def get_llm(self):
        """Return a ChatOpenAI instance with custom base_url."""
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=self.model,
            temperature=self.temperature,
            api_key=self.api_key,
            base_url=self.base_url,
            **self.kwargs
        )


class CompanyLLMProvider(BaseLLMProvider):
    """
    Company LLM Provider using the custom ChatCompanyLLM.
    
    This provider uses the ChatCompanyLLM class which extends BaseChatModel
    and communicates with the company's proprietary API format.
    
    Available models:
    - Gauss2.3
    - Gauss2.3 Think
    - GaussO Flash
    - GaussO Flash (S)
    - GaussO4
    - GaussO4 Thinking
    
    Or use custom_model_id and custom_model_url for additional models.
    """
    
    def __init__(self, model: str = "Gauss2.3", temperature: float = 0,
                 api_key: Optional[str] = None,
                 custom_model_id: Optional[str] = None,
                 custom_model_url: Optional[str] = None,
                 **kwargs):
        super().__init__(model, temperature, **kwargs)
        self.api_key = api_key or os.getenv("COMPANY_LLM_API_KEY")
        self.custom_model_id = custom_model_id or os.getenv("COMPANY_LLM_MODEL_ID")
        self.custom_model_url = custom_model_url or os.getenv("COMPANY_LLM_MODEL_URL")
        
        if not self.api_key:
            raise RuntimeError("COMPANY_LLM_API_KEY not set. Please set it in your .env file.")
    
    def get_llm(self):
        """Return a ChatCompanyLLM instance."""
        from company_chat_model import ChatCompanyLLM
        
        return ChatCompanyLLM(
            model=self.model,
            api_key=self.api_key,
            temperature=self.temperature,
            custom_model_id=self.custom_model_id,
            custom_model_url=self.custom_model_url,
            **self.kwargs
        )


class LLMFactory:
    """
    Factory class for creating LLM instances.
    
    Usage:
        llm = LLMFactory.create("gemini", model="gemini-1.5-flash")
        response = llm.invoke("Hello!")
    
    Or use the convenience function:
        llm = get_llm()  # Reads from environment variables
    """
    
    PROVIDERS = {
        "openai": OpenAIProvider,
        "gemini": GeminiProvider,
        "ollama": OllamaProvider,
        "custom": CustomLLMProvider,
        "company": CompanyLLMProvider,
    }
    
    @classmethod
    def create(cls, provider: str, model: Optional[str] = None, 
               temperature: float = 0, **kwargs) -> BaseLLMProvider:
        """
        Create an LLM provider instance.
        
        Args:
            provider: Provider name ("openai", "gemini", "ollama", "custom")
            model: Model name (provider-specific defaults used if not provided)
            temperature: Sampling temperature (default: 0)
            **kwargs: Additional provider-specific arguments
            
        Returns:
            An LLM provider instance
            
        Raises:
            ValueError: If provider is not supported
        """
        provider_lower = provider.lower()
        
        if provider_lower not in cls.PROVIDERS:
            available = ", ".join(cls.PROVIDERS.keys())
            raise ValueError(
                f"Unsupported LLM provider: '{provider}'. "
                f"Available providers: {available}"
            )
        
        provider_class = cls.PROVIDERS[provider_lower]
        
        # Use default model if not specified
        if model is None:
            model = cls._get_default_model(provider_lower)
        
        return provider_class(model=model, temperature=temperature, **kwargs)
    
    @classmethod
    def _get_default_model(cls, provider: str) -> str:
        """Get the default model for a provider."""
        defaults = {
            "openai": "gpt-4o-mini",
            "gemini": "gemini-1.5-flash",
            "ollama": "llama2",
            "custom": "custom-model",
        }
        return defaults.get(provider, "unknown")
    
    @classmethod
    def register_provider(cls, name: str, provider_class: type):
        """
        Register a new LLM provider.
        
        Use this to add your own custom provider at runtime.
        
        Args:
            name: Provider name (will be converted to lowercase)
            provider_class: Provider class (must inherit from BaseLLMProvider)
        """
        cls.PROVIDERS[name.lower()] = provider_class


# Convenience function for backward compatibility and easy usage
def get_llm(provider: Optional[str] = None, model: Optional[str] = None,
            temperature: Optional[float] = None) -> BaseLLMProvider:
    """
    Get an LLM instance based on environment variables or parameters.
    
    This function reads from environment variables by default:
    - LLM_PROVIDER: Provider name (default: "gemini")
    - LLM_MODEL: Model name (provider-specific default if not set)
    - LLM_TEMPERATURE: Temperature (default: 0)
    
    Args:
        provider: Override LLM_PROVIDER environment variable
        model: Override LLM_MODEL environment variable
        temperature: Override LLM_TEMPERATURE environment variable
        
    Returns:
        An LLM provider instance with a get_llm() method
        
    Example:
        # In .env file:
        LLM_PROVIDER=gemini
        LLM_MODEL=gemini-1.5-flash
        
        # In code:
        llm_provider = get_llm()
        llm = llm_provider.get_llm()
        response = llm.invoke("Hello!")
    """
    # Import here to avoid circular imports
    from config import LLM_PROVIDER, LLM_MODEL
    
    # Use parameters or fall back to config
    actual_provider = provider or LLM_PROVIDER
    actual_model = model or LLM_MODEL
    actual_temperature = temperature if temperature is not None else 0
    
    return LLMFactory.create(actual_provider, model=actual_model, temperature=actual_temperature)


# Export classes for easy importing
__all__ = [
    'BaseLLMProvider',
    'OpenAIProvider', 
    'GeminiProvider',
    'OllamaProvider',
    'CustomLLMProvider',
    'LLMFactory',
    'get_llm',
]