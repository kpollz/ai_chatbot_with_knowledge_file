"""
HTTP client for Company LLM (Gauss).

All logic mirrored from production code:
  machine-issue-solver/chatbot/app/company_chat_model.py
  machine-issue-solver/streaming_sample.py

Two modes:
  - call()          : non-streaming, returns full text
  - stream_call()   : streaming generator, yields text chunks
"""

import json
import logging
from typing import Generator

import httpx
import requests

from config import DEFAULT_TEMPERATURE, DEFAULT_TOP_P, REQUEST_TIMEOUT, SSL_VERIFY

logger = logging.getLogger("gauss-proxy")


# ── Request builder ──────────────────────────────────────────────────────────
# Ref: company_chat_model.py _build_request_body() lines 55-71

def build_request_body(
    model_id: str,
    input_value: str,
    system_message: str = "",
    temperature: float = DEFAULT_TEMPERATURE,
    top_p: float = DEFAULT_TOP_P,
    stream: bool = False,
) -> dict:
    """Build Company LLM request body.

    NOTE: `parameters` is a JSON *string*, not an object.
    This matches production behavior in company_chat_model.py line 66.
    """
    params_dict = {"temperature": temperature, "top_p": top_p}
    if stream:
        # Ref: company_chat_model.py lines 59-60
        params_dict["extra_body"] = {"repetition_penalty": 1.05}

    return {
        "component_inputs": {
            model_id: {
                "input_value": input_value,
                # Ref: company_chat_model.py line 65
                "max_retries": 0 if stream else 3,
                "parameters": json.dumps(params_dict),
                "stream": stream,
                "system_message": system_message,
            }
        }
    }


# ── Response parser ──────────────────────────────────────────────────────────
# Ref: company_chat_model.py _parse_response() lines 88-105

def parse_response(response_data: dict) -> str:
    """Extract text from Company LLM non-streaming response.

    Handles both formats:
      Format A: results.message.text is a dict  -> text.text
      Format B: results.message.text is a string -> use directly
    """
    try:
        result = response_data["outputs"][0]["outputs"][0]["results"]
        message = result["message"]
        text_field = message["text"]
        if isinstance(text_field, dict):
            return text_field["text"]
        return text_field
    except (KeyError, IndexError, TypeError) as e:
        logger.error(f"Unexpected response: {json.dumps(response_data, default=str)[:500]}")
        raise RuntimeError(f"Unexpected response format from Company LLM: {e}")


# ── Non-Streaming call ───────────────────────────────────────────────────────
# Ref: company_chat_model.py _generate() lines 154-176

def call(
    model_url: str,
    model_id: str,
    api_key: str,
    input_value: str,
    system_message: str = "",
    temperature: float = DEFAULT_TEMPERATURE,
    top_p: float = DEFAULT_TOP_P,
) -> str:
    """Call Company LLM (non-streaming) and return the full text response."""
    headers = {"Content-Type": "application/json", "x-api-key": api_key}
    params = {"stream": "false"}
    body = build_request_body(
        model_id=model_id,
        input_value=input_value,
        system_message=system_message,
        temperature=temperature,
        top_p=top_p,
        stream=False,
    )

    logger.info(f"Calling Company LLM (non-streaming): model_id={model_id}")

    # Ref: company_chat_model.py lines 165-170 — uses httpx with verify=False
    with httpx.Client(timeout=REQUEST_TIMEOUT, verify=SSL_VERIFY) as client:
        response = client.post(model_url, params=params, headers=headers, json=body)
        response.raise_for_status()

    return parse_response(response.json())


# ── Streaming call ───────────────────────────────────────────────────────────
# Ref: company_chat_model.py _stream() lines 109-150
# Ref: streaming_sample.py lines 67-83

def stream_call(
    model_url: str,
    model_id: str,
    api_key: str,
    input_value: str,
    system_message: str = "",
    temperature: float = DEFAULT_TEMPERATURE,
    top_p: float = DEFAULT_TOP_P,
) -> Generator[str, None, None]:
    """Call Company LLM (streaming) and yield text chunks.

    Uses `requests` library (not httpx) for streaming — same as production code.
    """
    headers = {"Content-Type": "application/json", "x-api-key": api_key}
    params = {"stream": "true"}
    body = build_request_body(
        model_id=model_id,
        input_value=input_value,
        system_message=system_message,
        temperature=temperature,
        top_p=top_p,
        stream=True,
    )

    logger.info(f"Calling Company LLM (streaming): model_id={model_id}")

    # Ref: company_chat_model.py lines 126-130 and streaming_sample.py lines 67-74
    # MUST use: verify=False, proxies={"https": None}, stream=True
    with requests.post(
        url=model_url,
        params=params,
        headers=headers,
        json=body,
        stream=True,
        verify=SSL_VERIFY,
        proxies={"https": None},
        timeout=REQUEST_TIMEOUT,
    ) as response:
        response.raise_for_status()

        for line in response.iter_lines():
            # Ref: streaming_sample.py lines 76-83
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
