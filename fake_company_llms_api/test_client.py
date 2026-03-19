"""
Test client for the Fake Company LLMs API.
This script mimics the original company_llms_sample_request.py format.
"""

import requests


API_KEY = "my-api-key"
BASE_URL = "http://localhost:8000"

LIST_MODELS = {
    "model-name": {
        "model-id": "model-id",
        "model-url": f"{BASE_URL}/api/v1/run/session_id"
    },
    "Gauss2.3": {
        "model-id": "gauss-2-3-id",
        "model-url": f"{BASE_URL}/api/v1/run/session_id"
    },
    "Gauss2.3 Think": {
        "model-id": "gauss-2-3-think-id",
        "model-url": f"{BASE_URL}/api/v1/run/session_id"
    },
    "GaussO Flash": {
        "model-id": "gauss-o-flash-id",
        "model-url": f"{BASE_URL}/api/v1/run/session_id"
    },
    "GaussO Flash (S)": {
        "model-id": "gauss-o-flash-s-id",
        "model-url": f"{BASE_URL}/api/v1/run/session_id"
    },
    "GaussO4": {
        "model-id": "gauss-o4-id",
        "model-url": f"{BASE_URL}/api/v1/run/session_id"
    },
    "GaussO4 Thinking": {
        "model-id": "gauss-o4-thinking-id",
        "model-url": f"{BASE_URL}/api/v1/run/session_id"
    },
}


def test_health():
    """Test the health endpoint."""
    response = requests.get(f"{BASE_URL}/health")
    print("Health Check:")
    print(f"  Status: {response.status_code}")
    print(f"  Response: {response.json()}")
    print()


def test_list_models():
    """Test the models listing endpoint."""
    response = requests.get(f"{BASE_URL}/api/v1/models")
    print("Available Models:")
    print(f"  Status: {response.status_code}")
    print(f"  Response: {response.json()}")
    print()


def test_run_model(model_name: str, user_prompt: str, system_prompt: str = ""):
    """Test running a model with the same format as company_llms_sample_request.py"""
    
    headers = {
        'Content-Type': 'application/json',
        'x-api-key': API_KEY
    }

    params = {
        'stream': 'false',
    }

    json_data = {
        'component_inputs': {
            LIST_MODELS[model_name]["model-id"]: {
                'input_value': user_prompt,
                'max_retries': 0,
                'parameters': '{"temperature":0, "top_p": 0.95, "extra_body": {"repetition_penalty":1.05}}',
                'stream': False,
                'system_message': system_prompt,
            }
        }
    }

    print(f"Testing model: {model_name}")
    print(f"User prompt: {user_prompt}")
    print(f"System prompt: {system_prompt or '(none)'}")
    print()

    response = requests.post(
        LIST_MODELS[model_name]["model-url"],
        params=params,
        headers=headers,
        json=json_data,
    )

    print(f"  Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"  Session ID: {data['session_id']}")
        
        # Extract the text response the same way as the original
        text_response = data['outputs'][0]['outputs'][0]['results']['text']['text']
        print(f"  Response text: {text_response}")
        print(f"  Full response: {data}")
    else:
        print(f"  Error: {response.text}")
    
    print()
    return response


def main():
    """Run all tests."""
    print("=" * 60)
    print("Fake Company LLMs API - Test Client")
    print("=" * 60)
    print()

    # Test health endpoint
    test_health()

    # Test list models
    test_list_models()

    # Test various prompts
    test_run_model("model-name", "who are you?")
    test_run_model("Gauss2.3", "Hello there!")
    test_run_model("GaussO4 Thinking", "What is the weather today?", system_prompt="You are a helpful assistant.")
    test_run_model("GaussO Flash", "Tell me about machine learning")


if __name__ == "__main__":
    main()