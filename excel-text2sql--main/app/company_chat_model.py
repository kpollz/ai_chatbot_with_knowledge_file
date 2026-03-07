"""
Custom Chat Model for Company LLM

This module implements a LangChain-compatible ChatModel for the company's proprietary LLM.
It extends BaseChatModel to integrate seamlessly with LangChain's ecosystem.
"""

import requests
import time
from typing import Any, List, Optional, Dict
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatResult, ChatGeneration
from pydantic import Field


# Available models configuration
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


class ChatCompanyLLM(BaseChatModel):
    """
    A LangChain-compatible ChatModel for the company's proprietary LLM.
    
    This class extends BaseChatModel to provide seamless integration with
    LangChain's ecosystem while communicating with the company's API.
    
    Example:
        llm = ChatCompanyLLM(
            model="Gauss2.3",
            api_key="your-api-key",
            temperature=0
        )
        
        response = llm.invoke("Hello, who are you?")
        print(response.content)
    """
    
    # Configuration fields
    model: str = Field(default="Gauss2.3", description="Model name from COMPANY_MODELS")
    api_key: str = Field(default="", description="API key for authentication")
    temperature: float = Field(default=0, ge=0, le=2, description="Sampling temperature")
    top_p: float = Field(default=0.95, ge=0, le=1, description="Top-p sampling")
    max_retries: int = Field(default=3, description="Maximum retry attempts")
    timeout: int = Field(default=60, description="Request timeout in seconds")
    stream: bool = Field(default=False, description="Enable streaming (not yet supported)")
    
    # Custom model configuration (if using custom URL)
    custom_model_id: Optional[str] = Field(default=None, description="Custom model ID")
    custom_model_url: Optional[str] = Field(default=None, description="Custom model URL")
    
    @property
    def _llm_type(self) -> str:
        """Return identifier for this LLM type."""
        return "company-llm"
    
    @property
    def _identifying_params(self) -> Dict[str, Any]:
        """Return identifying parameters for caching/tracking."""
        return {
            "model": self.model,
            "temperature": self.temperature,
            "top_p": self.top_p,
        }
    
    def _get_model_config(self) -> Dict[str, str]:
        """Get model configuration (ID and URL)."""
        if self.custom_model_id and self.custom_model_url:
            return {
                "model-id": self.custom_model_id,
                "model-url": self.custom_model_url
            }
        
        if self.model not in COMPANY_MODELS:
            available = ", ".join(COMPANY_MODELS.keys())
            raise ValueError(f"Unknown model: '{self.model}'. Available models: {available}")
        
        return COMPANY_MODELS[self.model]
    
    def _build_request_body(self, user_prompt: str, system_prompt: str = "") -> Dict[str, Any]:
        """Build the request body for the API call."""
        model_config = self._get_model_config()
        
        return {
            'component_inputs': {
                model_config["model-id"]: {
                    'input_value': user_prompt,
                    'max_retries': self.max_retries,
                    'parameters': f'{{"temperature":{self.temperature}, "top_p": {self.top_p}, "extra_body": {{"repetition_penalty":1.05}}}}',
                    'stream': self.stream,
                    'system_message': system_prompt,
                }
            }
        }
    
    def _call_api(self, user_prompt: str, system_prompt: str = "") -> str:
        """Make the API call and return the response text."""
        from logger import logger
        
        model_config = self._get_model_config()
        
        headers = {
            'Content-Type': 'application/json',
            'x-api-key': self.api_key
        }
        
        params = {
            'stream': 'false',
        }
        
        json_data = self._build_request_body(user_prompt, system_prompt)
        
        start_time = time.time()
        logger.info(f"Calling Company LLM API: {self.model}")
        
        response = requests.post(
            model_config["model-url"],
            params=params,
            headers=headers,
            json=json_data,
            timeout=self.timeout
        )
        
        response.raise_for_status()
        
        # Parse response
        response_data = response.json()
        
        # Extract text from nested response structure
        try:
            text = response_data['outputs'][0]['outputs'][0]['results']['text']['text']
            elapsed = time.time() - start_time
            logger.info(f"Company LLM response received in {elapsed:.2f}s")
            return text
        except (KeyError, IndexError) as e:
            raise RuntimeError(f"Unexpected response format: {e}. Response: {response_data}")
    
    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """
        Generate a response from the company LLM.
        
        Args:
            messages: List of LangChain messages (HumanMessage, SystemMessage, etc.)
            stop: Optional stop sequences (not used in this implementation)
            run_manager: Optional run manager for callbacks
            **kwargs: Additional generation parameters
            
        Returns:
            ChatResult containing the generated message
        """
        # Extract system prompt and user prompt from messages
        system_prompt = ""
        user_prompt = ""
        
        for message in messages:
            if isinstance(message, SystemMessage):
                system_prompt = message.content
            elif isinstance(message, HumanMessage):
                user_prompt = message.content
            else:
                # For other message types, append to user prompt
                user_prompt += f"\n{message.content}"
        
        if not user_prompt:
            raise ValueError("No user message provided")
        
        # Call the API
        response_text = self._call_api(user_prompt, system_prompt)
        
        # Create the response message
        message = AIMessage(content=response_text)
        
        # Return as ChatResult
        generation = ChatGeneration(message=message)
        return ChatResult(generations=[generation])
    
    def _stream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs: Any,
    ):
        """Stream responses (not yet implemented for company LLM)."""
        raise NotImplementedError("Streaming is not yet supported for company LLM. Use invoke() instead.")
    
    @property
    def _default_params(self) -> Dict[str, Any]:
        """Get default parameters for generation."""
        return {
            "temperature": self.temperature,
            "top_p": self.top_p,
        }


def get_company_llm(
    model: str = "Gauss2.3",
    api_key: Optional[str] = None,
    temperature: float = 0,
    **kwargs
) -> ChatCompanyLLM:
    """
    Convenience function to create a company LLM instance.
    
    Args:
        model: Model name from COMPANY_MODELS (default: "Gauss2.3")
        api_key: API key (reads from COMPANY_LLM_API_KEY env var if not provided)
        temperature: Sampling temperature (default: 0)
        **kwargs: Additional parameters
        
    Returns:
        ChatCompanyLLM instance
    """
    import os
    
    actual_api_key = api_key or os.getenv("COMPANY_LLM_API_KEY", "")
    
    return ChatCompanyLLM(
        model=model,
        api_key=actual_api_key,
        temperature=temperature,
        **kwargs
    )