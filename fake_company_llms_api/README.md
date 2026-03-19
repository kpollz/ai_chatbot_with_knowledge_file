# Fake Company LLMs API

A FastAPI mock server that mimics the company's LLMs API format. This is useful for testing and development when you don't have access to the real company LLMs API.

## Features

- Mimics the exact request/response format of the company's LLMs API
- Supports all model endpoints (Gauss2.3, GaussO Flash, GaussO4, etc.)
- API key validation
- Health check endpoint
- Easy to customize response logic

## Installation

1. Create a virtual environment (recommended):

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

## Running the Server

### Option 1: Using uvicorn directly

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Option 2: Running the main.py directly

```bash
python main.py
```

The server will start at `http://localhost:8000`

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | API information |
| `/health` | GET | Health check |
| `/api/v1/models` | GET | List available models |
| `/api/v1/run/{session_id}` | POST | Run a model (main endpoint) |

## Usage

### Using the test client

After starting the server, run the test client in a new terminal:

```bash
python test_client.py
```

### Using requests (like the original format)

```python
import requests

API_KEY = "my-api-key"
BASE_URL = "http://localhost:8000"

headers = {
    'Content-Type': 'application/json',
    'x-api-key': API_KEY
}

params = {
    'stream': 'false',
}

json_data = {
    'component_inputs': {
        'model-id': {
            'input_value': 'who are you?',
            'max_retries': 0,
            'parameters': '{"temperature":0, "top_p": 0.95, "extra_body": {"repetition_penalty":1.05}}',
            'stream': False,
            'system_message': '',
        }
    }
}

response = requests.post(
    f"{BASE_URL}/api/v1/run/session_id",
    params=params,
    headers=headers,
    json=json_data,
)

# Extract the response text
data = response.json()
text = data['outputs'][0]['outputs'][0]['results']['text']['text']
print(text)
```

### Using curl

```bash
curl -X POST "http://localhost:8000/api/v1/run/test-session?stream=false" \
  -H "Content-Type: application/json" \
  -H "x-api-key: my-api-key" \
  -d '{
    "component_inputs": {
      "model-id": {
        "input_value": "who are you?",
        "max_retries": 0,
        "parameters": "{\"temperature\":0, \"top_p\": 0.95, \"extra_body\": {\"repetition_penalty\":1.05}}",
        "stream": false,
        "system_message": ""
      }
    }
  }'
```

## Response Format

The API returns responses in the exact format of the company's LLMs API:

```json
{
  "session_id": "session_id",
  "outputs": [
    {
      "inputs": {},
      "outputs": [
        {
          "results": {
            "text": {
              "text": "The LLM response text here",
              "sender": null,
              "sender_name": null,
              "timestamp": "2024-01-01T12:00:00.000000",
              "error": false
            }
          },
          "timedelta": null,
          "duration": null,
          "component_display_name": "Text Output",
          "component_id": "uuid-here"
        }
      ],
      "legacy_components": [],
      "warning": null
    }
  ]
}
```

## Customizing Responses

To customize the mock responses, edit the `generate_fake_response()` function in `main.py`:

```python
def generate_fake_response(user_prompt: str, system_message: str, model_id: str) -> dict:
    """Generate a fake LLM response based on the user prompt."""
    
    # Add your custom logic here
    if "your keyword" in user_prompt.lower():
        return "Your custom response"
    
    # Default response
    return f"[Mock Response] You said: '{user_prompt}'"
```

## Available Models

The mock server supports these models (matching the company's model list):

- `model-name`
- `Gauss2.3`
- `Gauss2.3 Think`
- `GaussO Flash`
- `GaussO Flash (S)`
- `GaussO4`
- `GaussO4 Thinking`

## API Documentation

Once the server is running, you can access:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## License

MIT License