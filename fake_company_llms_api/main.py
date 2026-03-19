"""
Fake Company LLMs API - A FastAPI mock server that mimics the company's LLMs API format.
"""

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Dict, Any, Optional
from datetime import datetime
import uuid
import asyncio

app = FastAPI(
    title="Fake Company LLMs API",
    description="A mock API that mimics the company's LLMs response format",
    version="1.0.0"
)

# Configuration
API_KEY = "my-api-key"

# Available models
LIST_MODELS = {
    "model-name": {
        "model-id": "model-id",
        "model-url": "/api/v1/run/session_id"
    },
    "Gauss2.3": {
        "model-id": "gauss-2-3-id",
        "model-url": "/api/v1/run/session_id"
    },
    "Gauss2.3 Think": {
        "model-id": "gauss-2-3-think-id",
        "model-url": "/api/v1/run/session_id"
    },
    "GaussO Flash": {
        "model-id": "gauss-o-flash-id",
        "model-url": "/api/v1/run/session_id"
    },
    "GaussO Flash (S)": {
        "model-id": "gauss-o-flash-s-id",
        "model-url": "/api/v1/run/session_id"
    },
    "GaussO4": {
        "model-id": "gauss-o4-id",
        "model-url": "/api/v1/run/session_id"
    },
    "GaussO4 Thinking": {
        "model-id": "gauss-o4-thinking-id",
        "model-url": "/api/v1/run/session_id"
    },
}


# Request Models
class ModelInput(BaseModel):
    input_value: str
    max_retries: int = 0
    parameters: str = '{"temperature":0, "top_p": 0.95, "extra_body": {"repetition_penalty":1.05}}'
    stream: bool = False
    system_message: str = ""


class ComponentInputs(BaseModel):
    component_inputs: Dict[str, ModelInput]


# Response Models
class TextResult(BaseModel):
    text: str
    sender: Optional[str] = None
    sender_name: Optional[str] = None
    timestamp: str
    error: bool = False


class Results(BaseModel):
    text: TextResult


class OutputItem(BaseModel):
    results: Results
    timedelta: Optional[str] = None
    duration: Optional[str] = None
    component_display_name: str = "Text Output"
    component_id: str


class Output(BaseModel):
    inputs: Dict[str, Any] = {}
    outputs: list[OutputItem]
    legacy_components: list = []
    warning: Optional[str] = None


class RunResponse(BaseModel):
    session_id: str
    outputs: list[Output]


def generate_fake_response(user_prompt: str, system_message: str, model_id: str) -> dict:
    """Generate a fake LLM response based on the user prompt."""
    
    # Simple response logic - you can customize this
    if "who are you" in user_prompt.lower():
        response_text = f"I am a fake AI assistant running on model {model_id}. This is a mock response from the FastAPI server."
    elif "hello" in user_prompt.lower():
        response_text = f"Hello! I'm a mocked LLM response from {model_id}. How can I help you today?"
    elif "weather" in user_prompt.lower():
        response_text = "I'm sorry, I don't have access to real-time weather data as I'm just a mock server."
    else:
        response_text = f"[Mock Response from {model_id}] You said: '{user_prompt}'. This is a simulated response for testing purposes."
    
    # Add system message context if provided
    if system_message:
        response_text = f"[System context applied] {response_text}"
    
    return response_text


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "Fake Company LLMs API",
        "version": "1.0.0",
        "endpoints": {
            "run": "/api/v1/run/{session_id}",
            "models": "/api/v1/models",
            "health": "/health"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.get("/api/v1/models")
async def list_models():
    """List all available models."""
    return {
        "models": {name: {"model-id": info["model-id"]} for name, info in LIST_MODELS.items()}
    }


@app.post("/api/v1/run/{session_id}")
async def run_model(
    session_id: str,
    request_data: ComponentInputs,
    stream: bool = Query(default=False),
    x_api_key: str = Header(default=None, alias="x-api-key")
):
    """
    Run a model and return the response.
    
    This endpoint mimics the company's LLMs API format.
    """
    # Validate API key
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    # Get the model input (there should be one entry in component_inputs)
    if not request_data.component_inputs:
        raise HTTPException(status_code=400, detail="No component_inputs provided")
    
    # Get the first (and typically only) model input
    model_id = list(request_data.component_inputs.keys())[0]
    model_input = request_data.component_inputs[model_id]
    
    # Generate fake response
    response_text = generate_fake_response(
        user_prompt=model_input.input_value,
        system_message=model_input.system_message,
        model_id=model_id
    )
    
    # Simulate some processing time
    await asyncio.sleep(0.1)
    
    # Build the response matching the company's format
    response = {
        "session_id": session_id,
        "outputs": [
            {
                "inputs": {},
                "outputs": [
                    {
                        "results": {
                            "text": {
                                "text": response_text,
                                "sender": None,
                                "sender_name": None,
                                "timestamp": datetime.now().isoformat(),
                                "error": False
                            }
                        },
                        "timedelta": None,
                        "duration": None,
                        "component_display_name": "Text Output",
                        "component_id": str(uuid.uuid4())
                    }
                ],
                "legacy_components": [],
                "warning": None
            }
        ]
    }
    
    return JSONResponse(content=response)


@app.post("/api/v1/run_stream/{session_id}")
async def run_model_stream(
    session_id: str,
    request_data: ComponentInputs,
    stream: bool = Query(default=True),
    x_api_key: str = Header(default=None, alias="x-api-key")
):
    """
    Run a model with streaming response (mock implementation).
    
    Note: This is a simplified mock that returns the full response at once.
    """
    # Validate API key
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    # For now, just call the non-streaming version
    return await run_model(session_id, request_data, stream=False, x_api_key=x_api_key)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)