"""
Diagnostic script: Test LLM connection with and without Langfuse import.

This isolates whether the Langfuse import itself breaks the LLM connection.

Usage:
  cd chatbot
  python test_llm_connection.py
"""

import os
import sys
import json
import time
from pathlib import Path
from dotenv import load_dotenv

# Load .env
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)

LLM_MODEL = os.environ.get("LLM_MODEL", "Gauss2.3")
API_KEY = os.environ.get("COMPANY_LLM_API_KEY", "")
MODEL_ID = os.environ.get("COMPANY_LLM_MODEL_ID", "")
MODEL_URL = os.environ.get("COMPANY_LLM_MODEL_URL", "")

# Model registry (simplified)
COMPANY_MODELS = {
    "Gauss2.3": {
        "model-id": "model-gauss-2-3",
        "model-url": "https://api.company.com/v1/generate"
    },
}

def get_model_url():
    if MODEL_URL:
        return MODEL_URL
    if LLM_MODEL in COMPANY_MODELS:
        return COMPANY_MODELS[LLM_MODEL]["model-url"]
    return None

def get_model_id():
    if MODEL_ID:
        return MODEL_ID
    if LLM_MODEL in COMPANY_MODELS:
        return COMPANY_MODELS[LLM_MODEL]["model-id"]
    return None

def test_llm_stream(test_name: str):
    """Test LLM streaming connection."""
    url = get_model_url()
    model_id = get_model_id()
    
    if not url or not API_KEY:
        print(f"  ❌ Missing config: URL={'SET' if url else 'MISSING'}, API_KEY={'SET' if API_KEY else 'MISSING'}")
        return False
    
    headers = {'Content-Type': 'application/json', 'x-api-key': API_KEY}
    params = {'stream': 'true'}
    json_data = {
        'component_inputs': {
            model_id: {
                'input_value': 'Xin chào',
                'max_retries': 0,
                'parameters': json.dumps({"temperature": 0, "top_p": 0.95}),
                'stream': True,
                'system_message': 'Trả lời ngắn gọn.',
            }
        }
    }
    
    import requests as req_lib
    
    print(f"  URL: {url}")
    print(f"  Model ID: {model_id}")
    print(f"  API Key: ***{API_KEY[-4:] if len(API_KEY) > 4 else 'SHORT'}")
    print(f"  Opening connection...")
    
    try:
        resp = req_lib.post(
            url, params=params, headers=headers, json=json_data,
            stream=True, verify=False, proxies={"https": None},
            timeout=30,
        )
        print(f"  Status: {resp.status_code}")
        resp.raise_for_status()
        
        chunks = 0
        lines = 0
        for line in resp.iter_lines():
            if not line:
                continue
            lines += 1
            try:
                decoded = json.loads(line.decode("utf-8"))
                if decoded.get("event") == "token":
                    chunk = decoded["data"]["chunk"]
                    if chunk:
                        chunks += 1
                        if chunks <= 3:
                            print(f"  Chunk #{chunks}: '{chunk}'")
            except (json.JSONDecodeError, KeyError):
                pass
        
        resp.close()
        print(f"  ✅ SUCCESS! {chunks} chunks, {lines} lines")
        return True
        
    except Exception as e:
        print(f"  ❌ FAILED: {type(e).__name__}: {e}")
        return False


# ====== TEST 1: Without Langfuse ======
print("=" * 60)
print("TEST 1: LLM streaming WITHOUT Langfuse import")
print("=" * 60)
success1 = test_llm_stream("without_langfuse")

# ====== TEST 2: Import Langfuse, then test LLM ======
print()
print("=" * 60)
print("TEST 2: LLM streaming AFTER importing Langfuse")
print("=" * 60)
print("  Importing langfuse...")
try:
    from langfuse import observe, get_client, propagate_attributes
    print("  ✅ Langfuse imported successfully")
    
    # Try get_client
    try:
        client = get_client()
        print(f"  get_client() = {type(client).__name__}")
    except Exception as e:
        print(f"  get_client() failed: {e}")
    
except ImportError as e:
    print(f"  ❌ Langfuse import failed: {e}")
    success2 = False
else:
    success2 = test_llm_stream("with_langfuse")

# ====== TEST 3: With propagate_attributes context ======
print()
print("=" * 60)
print("TEST 3: LLM streaming INSIDE propagate_attributes context")
print("=" * 60)
try:
    success3 = False
    print("  Creating propagate_attributes context...")
    with propagate_attributes(session_id="test_session"):
        print("  Inside context, testing LLM...")
        success3 = test_llm_stream("with_propagate_attributes")
except Exception as e:
    print(f"  ❌ propagate_attributes failed: {type(e).__name__}: {e}")
    success3 = False

# ====== Summary ======
print()
print("=" * 60)
print("SUMMARY")
print("=" * 60)
print(f"  Test 1 (no Langfuse):     {'✅ PASS' if success1 else '❌ FAIL'}")
print(f"  Test 2 (with Langfuse):   {'✅ PASS' if success2 else '❌ FAIL'}")
print(f"  Test 3 (propagate_attrs): {'✅ PASS' if success3 else '❌ FAIL'}")
print()

if success1 and not success2:
    print("🔍 DIAGNOSIS: Langfuse IMPORT breaks LLM connection!")
    print("   → OpenTelemetry may be auto-instrumenting requests library")
elif success1 and success2 and not success3:
    print("🔍 DIAGNOSIS: propagate_attributes() context breaks LLM connection!")
    print("   → OpenTelemetry context attachment interferes with requests")
elif not success1:
    print("🔍 DIAGNOSIS: LLM connection fails even without Langfuse!")
    print("   → This is a network/server issue, not Langfuse-related")
elif success1 and success2 and success3:
    print("🔍 DIAGNOSIS: All tests passed! The issue may be intermittent")
    print("   → Try running multiple times or check Streamlit-specific behavior")