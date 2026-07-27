"""
LLM factory — returns an OpenAI-compatible chat model
(``langchain_openai.ChatOpenAI``) with native tool/function calling and token
streaming.

Configure via ``OPENAI_BASE_URL`` / ``OPENAI_API_KEY`` / ``OPENAI_MODEL``.
"""

from typing import Optional

from langchain_core.language_models.chat_models import BaseChatModel

from src import config
from src.logger import logger


def get_chat_model(temperature: Optional[float] = None) -> BaseChatModel:
    """Build the OpenAI-compatible chat model.

    Args:
        temperature: overrides ``config.LLM_TEMPERATURE``.
    """
    from langchain_openai import ChatOpenAI  # lazy import

    temp = config.LLM_TEMPERATURE if temperature is None else temperature
    if not config.OPENAI_MODEL:
        logger.warning("OPENAI_MODEL is empty — set it in the environment.")
    if not config.OPENAI_BASE_URL:
        logger.warning("OPENAI_BASE_URL is empty — falling back to the default OpenAI host.")

    return ChatOpenAI(
        model=config.OPENAI_MODEL,
        api_key=config.OPENAI_API_KEY or "not-needed",
        base_url=config.OPENAI_BASE_URL or None,
        temperature=temp,
        streaming=True,
        timeout=60,
        max_retries=2,
    )
