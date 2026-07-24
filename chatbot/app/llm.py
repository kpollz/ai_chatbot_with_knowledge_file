"""
LLM factory — returns a LangChain chat model based on LLM_PROVIDER.

  - "openai"  : any OpenAI-compatible endpoint via langchain_openai.ChatOpenAI.
                Supports native tool/function calling and token streaming.
  - "company" : legacy proprietary Gauss wrapper (text-based tool calling).

The heavy provider SDKs are imported lazily so importing this module never
requires a provider that the current deployment does not use.
"""

from typing import Optional

from langchain_core.language_models.chat_models import BaseChatModel

import config
from logger import logger


def get_chat_model(api_key: Optional[str] = None,
                   temperature: Optional[float] = None) -> BaseChatModel:
    """Build the configured chat model.

    Args:
        api_key: overrides the provider's configured key (e.g. the sidebar key).
        temperature: overrides ``config.LLM_TEMPERATURE``.
    """
    temp = config.LLM_TEMPERATURE if temperature is None else temperature
    provider = (config.LLM_PROVIDER or "openai").lower()

    if provider == "company":
        from company_chat_model import get_company_llm  # lazy
        return get_company_llm(
            model=config.LLM_MODEL,
            temperature=temp,
            api_key=api_key or config.COMPANY_LLM_API_KEY,
        )

    # Default: OpenAI-compatible endpoint
    from langchain_openai import ChatOpenAI  # lazy

    if not config.OPENAI_MODEL:
        logger.warning("OPENAI_MODEL is empty — set it in the environment (LLM_PROVIDER=openai).")
    if not config.OPENAI_BASE_URL:
        logger.warning("OPENAI_BASE_URL is empty — falling back to the default OpenAI host.")

    return ChatOpenAI(
        model=config.OPENAI_MODEL,
        api_key=api_key or config.OPENAI_API_KEY or "not-needed",
        base_url=config.OPENAI_BASE_URL or None,
        temperature=temp,
        streaming=True,
        timeout=60,
        max_retries=2,
    )
