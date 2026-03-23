"""
Custom Chat Model for Company LLM (async support via httpx, streaming via requests)
"""

import json
import time
from typing import Any, Generator, List, Optional, Dict

import httpx
import requests as req_lib
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

    def _build_request_body(self, user_prompt: str, system_prompt: str = "",
                            stream: bool = False) -> Dict[str, Any]:
        model_config = self._get_model_config()
        params_dict = {"temperature": self.temperature, "top_p": self.top_p}
        if stream:
            params_dict["extra_body"] = {"repetition_penalty": 1.05}
        return {
            'component_inputs': {
                model_config["model-id"]: {
                    'input_value': user_prompt,
                    'max_retries': self.max_retries if not stream else 0,
                    'parameters': json.dumps(params_dict),
                    'stream': stream,
                    'system_message': system_prompt,
                }
            }
        }

    def _parse_messages(self, messages: List[BaseMessage]) -> tuple[str, str]:
        """Extract system and user prompts from message list."""
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
        return user_prompt, system_prompt

    @staticmethod
    def _parse_response(response_data: dict) -> str:
        """Extract text from API response."""
        try:
            return response_data['outputs'][0]['outputs'][0]['results']['text']['text']
        except (KeyError, IndexError) as e:
            raise RuntimeError(f"Unexpected response format: {e}")

    # ---- Streaming (sync, using requests) ----

    def stream_chat(self, messages: List[BaseMessage]) -> Generator[str, None, None]:
        """Sync streaming generator — yields text chunks as they arrive from the API."""
        user_prompt, system_prompt = self._parse_messages(messages)
        model_config = self._get_model_config()
        headers = {'Content-Type': 'application/json', 'x-api-key': self.api_key}
        params = {'stream': 'true'}
        json_data = self._build_request_body(user_prompt, system_prompt, stream=True)

        start_time = time.time()
        logger.info(f"Calling Company LLM (streaming): {self.model}")

        with req_lib.post(
            model_config["model-url"],
            params=params, headers=headers, json=json_data,
            stream=True, verify=False, proxies={"https": None},
            timeout=self.timeout,
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line:
                    continue
                try:
                    decoded_line = json.loads(line.decode("utf-8"))
                    if decoded_line.get("event") == "token":
                        chunk = decoded_line["data"]["chunk"]
                        if chunk:
                            yield chunk
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning(f"Skipping malformed streaming line: {e}")

        logger.info(f"Streaming completed in {time.time() - start_time:.2f}s")

    def invoke_sync(self, messages: List[BaseMessage]) -> str:
        """Sync non-streaming call — returns full response text."""
        user_prompt, system_prompt = self._parse_messages(messages)
        model_config = self._get_model_config()
        headers = {'Content-Type': 'application/json', 'x-api-key': self.api_key}
        params = {'stream': 'false'}
        json_data = self._build_request_body(user_prompt, system_prompt, stream=False)

        start_time = time.time()
        logger.info(f"Calling Company LLM (sync): {self.model}")

        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                model_config["model-url"],
                params=params, headers=headers, json=json_data
            )
            response.raise_for_status()

        text = self._parse_response(response.json())
        logger.info(f"LLM response received in {time.time() - start_time:.2f}s")
        return text

    # ---- Sync (fallback, LangChain interface) ----

    def _generate(self, messages: List[BaseMessage], stop: Optional[List[str]] = None,
                  run_manager: Optional[Any] = None, **kwargs: Any) -> ChatResult:
        user_prompt, system_prompt = self._parse_messages(messages)
        model_config = self._get_model_config()
        headers = {'Content-Type': 'application/json', 'x-api-key': self.api_key}
        params = {'stream': 'false'}
        json_data = self._build_request_body(user_prompt, system_prompt)

        start_time = time.time()
        logger.info(f"Calling Company LLM (sync): {self.model}")

        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                model_config["model-url"],
                params=params, headers=headers, json=json_data
            )
            response.raise_for_status()

        text = self._parse_response(response.json())
        logger.info(f"LLM response received in {time.time() - start_time:.2f}s")

        message = AIMessage(content=text)
        return ChatResult(generations=[ChatGeneration(message=message)])

    # ---- Async (primary) ----

    async def _agenerate(self, messages: List[BaseMessage], stop: Optional[List[str]] = None,
                         run_manager: Optional[Any] = None, **kwargs: Any) -> ChatResult:
        user_prompt, system_prompt = self._parse_messages(messages)
        model_config = self._get_model_config()
        headers = {'Content-Type': 'application/json', 'x-api-key': self.api_key}
        params = {'stream': 'false'}
        json_data = self._build_request_body(user_prompt, system_prompt)

        start_time = time.time()
        logger.info(f"Calling Company LLM (async): {self.model}")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                model_config["model-url"],
                params=params, headers=headers, json=json_data
            )
            response.raise_for_status()

        text = self._parse_response(response.json())
        logger.info(f"LLM response received in {time.time() - start_time:.2f}s")

        message = AIMessage(content=text)
        return ChatResult(generations=[ChatGeneration(message=message)])


def get_company_llm(model: str = "Gauss2.3", api_key: Optional[str] = None,
                    temperature: float = 0, **kwargs) -> ChatCompanyLLM:
    actual_api_key = api_key or COMPANY_LLM_API_KEY
    return ChatCompanyLLM(
        model=model, api_key=actual_api_key, temperature=temperature,
        custom_model_id=COMPANY_LLM_MODEL_ID, custom_model_url=COMPANY_LLM_MODEL_URL, **kwargs
    )
