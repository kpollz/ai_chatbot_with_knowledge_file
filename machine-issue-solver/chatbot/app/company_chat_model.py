"""
Custom Chat Model for Company LLM

Implements LangChain's standard BaseChatModel interface:
  - _generate()  : sync non-streaming
  - _agenerate() : async non-streaming
  - _stream()    : sync streaming (yields ChatGenerationChunk)

Once _stream() is implemented, LangChain's .stream() method works automatically,
and Streamlit's st.write_stream(llm.stream(...)) handles display natively.
"""

import json
import time
from typing import Any, Iterator, List, Optional, Dict

import httpx
import requests as req_lib
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, AIMessage, AIMessageChunk, HumanMessage, SystemMessage
from langchain_core.outputs import ChatResult, ChatGeneration, ChatGenerationChunk
from langfuse import observe, get_client
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
        """Extract text from API response.

        Handles both formats:
          results.message.text.text  (text is a dict with nested 'text' key)
          results.message.text       (text is directly a string)
        """
        try:
            result = response_data['outputs'][0]['outputs'][0]['results']
            message = result['message']
            text_field = message['text']
            if isinstance(text_field, dict):
                return text_field['text']
            return text_field
        except (KeyError, IndexError, TypeError) as e:
            logger.error(f"Response structure: {json.dumps(response_data, default=str)[:500]}")
            raise RuntimeError(f"Unexpected response format: {e}")

    # ---- Streaming (LangChain standard interface) ----

    def _stream(self, messages: List[BaseMessage], stop: Optional[List[str]] = None,
                run_manager: Optional[Any] = None, **kwargs: Any) -> Iterator[ChatGenerationChunk]:
        """
        LangChain streaming interface — yields ChatGenerationChunk.

        This makes llm.stream(messages) work, which yields AIMessageChunk.
        Streamlit's st.write_stream() natively handles AIMessageChunk.
        
        Note: @observe is NOT used here because this is a generator function.
        Langfuse v4's @observe decorator may not handle generators correctly
        (it could consume the generator or interfere with streaming).
        Instead, we manually trace via the parent @observe in graph.py.
        """
        user_prompt, system_prompt = self._parse_messages(messages)
        model_config = self._get_model_config()
        headers = {'Content-Type': 'application/json', 'x-api-key': self.api_key}
        params = {'stream': 'true'}
        json_data = self._build_request_body(user_prompt, system_prompt, stream=True)

        start_time = time.time()
        logger.info(f"Calling Company LLM (streaming): {self.model}")

        last_error = None
        for attempt in range(self.max_retries + 1):
            chunks_yielded = False
            try:
                resp = req_lib.post(
                    model_config["model-url"],
                    params=params, headers=headers, json=json_data,
                    stream=True, verify=False, proxies={"https": None},
                    timeout=self.timeout,
                )
                resp.raise_for_status()

                line_count = 0
                for line in resp.iter_lines():
                    if not line:
                        continue
                    line_count += 1
                    try:
                        decoded_line = json.loads(line.decode("utf-8"))
                        if decoded_line.get("event") == "token":
                            chunk_text = decoded_line["data"]["chunk"]
                            if chunk_text:
                                chunks_yielded = True
                                chunk = ChatGenerationChunk(
                                    message=AIMessageChunk(content=chunk_text)
                                )
                                if run_manager:
                                    run_manager.on_llm_new_token(chunk_text, chunk=chunk)
                                yield chunk
                        elif decoded_line.get("event") == "error":
                            logger.error(f"LLM server error event: {decoded_line}")
                    except (json.JSONDecodeError, KeyError) as e:
                        logger.warning(f"Skipping malformed streaming line: {e}")

                logger.info(f"Streaming completed in {time.time() - start_time:.2f}s, {line_count} lines")
                resp.close()
                return  # Success

            except (req_lib.exceptions.ConnectionError, ConnectionResetError) as e:
                last_error = e
                logger.warning(f"LLM connection error (attempt {attempt + 1}/{self.max_retries + 1}): {e}")
                # Only retry if no chunks have been yielded yet
                if not chunks_yielded and attempt < self.max_retries:
                    wait_time = 2 ** attempt
                    logger.info(f"Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"LLM connection failed after {attempt + 1} attempts")
                    raise
            except req_lib.exceptions.HTTPError as e:
                logger.error(f"LLM HTTP error {e.response.status_code}: {e.response.text[:500]}")
                raise
            except Exception as e:
                logger.error(f"LLM streaming error: {type(e).__name__}: {e}", exc_info=True)
                raise

        # All retries exhausted
        raise ConnectionError(f"Company LLM unreachable after {self.max_retries + 1} attempts. Last error: {last_error}")

    # ---- Sync (LangChain interface) ----

    @observe(name="llm_generate", as_type="generation")
    def _generate(self, messages: List[BaseMessage], stop: Optional[List[str]] = None,
                  run_manager: Optional[Any] = None, **kwargs: Any) -> ChatResult:
        """
        LangChain sync interface — returns ChatResult.
        
        Langfuse v4: @observe with as_type="generation" auto-captures inputs/outputs.
        Use get_client().update_current_generation() for metadata/model info.
        """
        user_prompt, system_prompt = self._parse_messages(messages)
        model_config = self._get_model_config()
        headers = {'Content-Type': 'application/json', 'x-api-key': self.api_key}
        params = {'stream': 'false'}
        json_data = self._build_request_body(user_prompt, system_prompt)

        # Update current generation with model info (Langfuse v4 pattern)
        try:
            lf_client = get_client()
            lf_client.update_current_generation(
                model=self.model,
                metadata={"temperature": str(self.temperature), "top_p": str(self.top_p), "stream": "false"}
            )
        except Exception as lf_err:
            logger.debug(f"Langfuse update skipped: {lf_err}")

        start_time = time.time()
        logger.info(f"Calling Company LLM (sync): {self.model}")

        with httpx.Client(timeout=self.timeout, verify=False) as http_client:
            response = http_client.post(
                model_config["model-url"],
                params=params, headers=headers, json=json_data
            )
            response.raise_for_status()

        text = self._parse_response(response.json())
        logger.info(f"LLM response received in {time.time() - start_time:.2f}s")

        # Return result - @observe auto-captures return value as output
        message = AIMessage(content=text)
        return ChatResult(generations=[ChatGeneration(message=message)])

    # ---- Async (LangChain interface) ----

    async def _agenerate(self, messages: List[BaseMessage], stop: Optional[List[str]] = None,
                         run_manager: Optional[Any] = None, **kwargs: Any) -> ChatResult:
        user_prompt, system_prompt = self._parse_messages(messages)
        model_config = self._get_model_config()
        headers = {'Content-Type': 'application/json', 'x-api-key': self.api_key}
        params = {'stream': 'false'}
        json_data = self._build_request_body(user_prompt, system_prompt)

        start_time = time.time()
        logger.info(f"Calling Company LLM (async): {self.model}")

        async with httpx.AsyncClient(timeout=self.timeout, verify=False) as client:
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
