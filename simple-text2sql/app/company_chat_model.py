"""Company LLM Chat Model"""

import time
import requests
from typing import Any, List, Optional, Dict
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatResult, ChatGeneration
from pydantic import Field

from config import COMPANY_LLM_API_KEY, COMPANY_LLM_MODEL_ID, COMPANY_LLM_MODEL_URL
from logger import logger

COMPANY_MODELS = {
    "Gauss2.3": {"model-id": "model-id", "model-url": "https://mycompany.com/api/v1/run/session_id"},
    "Gauss2.3 Think": {"model-id": "model-id", "model-url": "https://mycompany.com/api/v1/run/session_id"},
    "GaussO Flash": {"model-id": "model-id", "model-url": "https://mycompany.com/api/v1/run/session_id"},
    "GaussO4": {"model-id": "model-id", "model-url": "https://mycompany.com/api/v1/run/session_id"},
}


class ChatCompanyLLM(BaseChatModel):
    model: str = Field(default="Gauss2.3")
    api_key: str = Field(default="")
    temperature: float = Field(default=0)
    timeout: int = Field(default=60)
    custom_model_id: Optional[str] = Field(default=None)
    custom_model_url: Optional[str] = Field(default=None)

    @property
    def _llm_type(self) -> str:
        return "company-llm"

    def _get_model_config(self) -> Dict[str, str]:
        if self.custom_model_id and self.custom_model_url:
            return {"model-id": self.custom_model_id, "model-url": self.custom_model_url}
        return COMPANY_MODELS.get(self.model, COMPANY_MODELS["Gauss2.3"])

    def _call_api(self, prompt: str, system: str = "") -> str:
        config = self._get_model_config()
        headers = {"Content-Type": "application/json", "x-api-key": self.api_key}
        data = {
            "component_inputs": {
                config["model-id"]: {
                    "input_value": prompt,
                    "parameters": f'{{"temperature":{self.temperature}}}',
                    "system_message": system,
                }
            }
        }
        
        logger.info(f"Calling Company LLM: {self.model}")
        start_time = time.time()
        
        try:
            resp = requests.post(config["model-url"], headers=headers, json=data, timeout=self.timeout)
            resp.raise_for_status()
            
            elapsed = time.time() - start_time
            logger.info(f"LLM response received in {elapsed:.2f}s")
            
            result = resp.json()["outputs"][0]["outputs"][0]["results"]["text"]["text"]
            logger.debug(f"Response length: {len(result)} chars")
            return result
            
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"LLM API call failed after {elapsed:.2f}s: {e}")
            raise

    def _generate(self, messages: List[BaseMessage], **kwargs) -> ChatResult:
        logger.info(f"Generating response for {len(messages)} messages")
        
        system, user = "", ""
        for m in messages:
            if isinstance(m, SystemMessage):
                system = m.content
                logger.debug("Found system message")
            elif isinstance(m, HumanMessage):
                user = m.content
                logger.debug(f"User message: {user[:50]}...")
        
        text = self._call_api(user, system)
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=text))])


def get_llm():
    logger.info("Creating LLM instance")
    return ChatCompanyLLM(
        model="Gauss2.3",
        api_key=COMPANY_LLM_API_KEY,
        custom_model_id=COMPANY_LLM_MODEL_ID,
        custom_model_url=COMPANY_LLM_MODEL_URL
    )