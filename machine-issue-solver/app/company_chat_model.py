"""
Custom Chat Model for Company LLM
"""

import requests
import time
from typing import Any, List, Optional, Dict
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatResult, ChatGeneration
from pydantic import Field

from config import COMPANY_MODELS, COMPANY_LLM_API_KEY, COMPANY_LLM_MODEL_ID, COMPANY_LLM_MODEL_URL
from logger import logger


class ChatCompanyLLM(BaseChatModel):
    """LangChain-compatible ChatModel for company's proprietary LLM."""
    
    model: str = Field(default="Gauss2.3", description="Model name")
    api_key: str = Field(default="", description="API key")
    temperature: float = Field(default=0, ge=0, le=2, description="Temperature")
    top_p: float = Field(default=0.95, ge=0, le=1, description="Top-p")
    max_retries: int = Field(default=3, description="Max retries")
    timeout: int = Field(default=60, description="Timeout in seconds")
    custom_model_id: Optional[str] = Field(default=None, description="Custom model ID")
    custom_model_url: Optional[str] = Field(default=None, description="Custom model URL")
    
    @property
    def _llm_type(self) -> str:
        return "company-llm"
    
    @property
    def _identifying_params(self) -> Dict[str, Any]:
        return {"model": self.model, "temperature": self.temperature}
    
    def _get_model_config(self) -> Dict[str, str]:
        if self.custom_model_id and self.custom_model_url:
            return {"model-id": self.custom_model_id, "model-url": self.custom_model_url}
        if self.model not in COMPANY_MODELS:
            raise ValueError(f"Unknown model: {self.model}")
        return COMPANY_MODELS[self.model]
    
    def _build_request_body(self, user_prompt: str, system_prompt: str = "") -> Dict[str, Any]:
        model_config = self._get_model_config()
        return {
            'component_inputs': {
                model_config["model-id"]: {
                    'input_value': user_prompt,
                    'max_retries': self.max_retries,
                    'parameters': f'{{"temperature":{self.temperature}, "top_p": {self.top_p}}}',
                    'stream': False,
                    'system_message': system_prompt,
                }
            }
        }
    
    def _call_api(self, user_prompt: str, system_prompt: str = "") -> str:
        model_config = self._get_model_config()
        headers = {'Content-Type': 'application/json', 'x-api-key': self.api_key}
        params = {'stream': 'false'}
        json_data = self._build_request_body(user_prompt, system_prompt)
        
        start_time = time.time()
        logger.info(f"Calling Company LLM: {self.model}")
        
        response = requests.post(
            model_config["model-url"],
            params=params, headers=headers, json=json_data, timeout=self.timeout
        )
        response.raise_for_status()
        
        response_data = response.json()
        try:
            text = response_data['outputs'][0]['outputs'][0]['results']['text']['text']
            elapsed = time.time() - start_time
            logger.info(f"LLM response received in {elapsed:.2f}s")
            return text
        except (KeyError, IndexError) as e:
            raise RuntimeError(f"Unexpected response format: {e}")
    
    def _generate(self, messages: List[BaseMessage], stop: Optional[List[str]] = None,
                  run_manager: Optional[Any] = None, **kwargs: Any) -> ChatResult:
        system_prompt = ""
        user_prompt = ""
        
        for message in messages:
            if isinstance(message, SystemMessage):
                system_prompt = message.content
            elif isinstance(message, HumanMessage):
                user_prompt = message.content
            else:
                user_prompt += f"\n{message.content}"
        
        if not user_prompt:
            raise ValueError("No user message provided")
        
        response_text = self._call_api(user_prompt, system_prompt)
        message = AIMessage(content=response_text)
        generation = ChatGeneration(message=message)
        return ChatResult(generations=[generation])


def get_company_llm(model: str = "Gauss2.3", api_key: Optional[str] = None,
                    temperature: float = 0, **kwargs) -> ChatCompanyLLM:
    actual_api_key = api_key or COMPANY_LLM_API_KEY
    return ChatCompanyLLM(
        model=model, api_key=actual_api_key, temperature=temperature,
        custom_model_id=COMPANY_LLM_MODEL_ID, custom_model_url=COMPANY_LLM_MODEL_URL, **kwargs
    )