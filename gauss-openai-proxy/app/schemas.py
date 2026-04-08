"""
Pydantic schemas for OpenAI Chat Completions API format.

These define the contract between OpenClaw (client) and this proxy.
Ref: API_CONTRACT.md sections 2, 3
"""

from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ── Request ──────────────────────────────────────────────────────────────────


class ChatMessage(BaseModel):
    """A single message in the conversation.

    Accepts all OpenClaw message roles and content formats:
      - role: "system" | "developer" | "user" | "assistant" | "tool"
      - content: string OR array of content parts [{type: "text", text: "..."}]
      - Optional fields: tool_calls, tool_call_id (passed through for tool translation)
    """

    model_config = ConfigDict(extra="ignore")

    role: str
    content: Any = None  # str | list | None — normalized in message_normalize.py

    # Tool-related fields (optional, only present in specific roles)
    tool_calls: Optional[List[Any]] = None  # assistant messages with function calls
    tool_call_id: Optional[str] = None  # tool result messages


class ToolFunction(BaseModel):
    """OpenAI function definition within a tool."""

    model_config = ConfigDict(extra="ignore")

    name: str
    description: Optional[str] = None
    parameters: Optional[dict] = None


class Tool(BaseModel):
    """OpenAI tool definition."""

    model_config = ConfigDict(extra="ignore")

    type: str = "function"
    function: ToolFunction


class ChatCompletionRequest(BaseModel):
    """Full OpenAI Chat Completion request.

    Accepts all fields OpenClaw sends. Fields not relevant to Gauss
    are accepted but ignored (extra="ignore" + Optional fields).
    """

    model_config = ConfigDict(extra="ignore")

    # Required
    model: str
    messages: List[ChatMessage]

    # Forwarded to Gauss
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    stream: bool = False

    # Max tokens — OpenClaw sends max_completion_tokens (new) or max_tokens (old)
    max_tokens: Optional[int] = None
    max_completion_tokens: Optional[int] = None

    # Tool calling — processed by tool_translation.py
    tools: Optional[List[Tool]] = None
    tool_choice: Optional[Any] = None

    # Streaming options (OpenAI sends stream_options: {include_usage: true})
    stream_options: Optional[dict] = None

    @property
    def effective_max_tokens(self) -> Optional[int]:
        """Return whichever max tokens field was provided."""
        return self.max_completion_tokens or self.max_tokens


# ── Response (Non-Streaming) ─────────────────────────────────────────────────


class ResponseMessage(BaseModel):
    role: str = "assistant"
    content: Optional[str] = None
    tool_calls: Optional[List[dict]] = None


class Choice(BaseModel):
    index: int = 0
    message: ResponseMessage
    finish_reason: str = "stop"


class Usage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[Choice]
    usage: Usage = Field(default_factory=Usage)


# ── Response (Streaming Chunk) ───────────────────────────────────────────────


class DeltaMessage(BaseModel):
    role: Optional[str] = None
    content: Optional[str] = None
    tool_calls: Optional[List[dict]] = None


class StreamChoice(BaseModel):
    index: int = 0
    delta: DeltaMessage
    finish_reason: Optional[str] = None


class ChatCompletionChunk(BaseModel):
    id: str
    object: str = "chat.completion.chunk"
    created: int
    model: str
    choices: List[StreamChoice]


# ── Error ────────────────────────────────────────────────────────────────────


class ErrorDetail(BaseModel):
    message: str
    type: str
    code: Optional[str] = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


# ── Models List ──────────────────────────────────────────────────────────────


class ModelObject(BaseModel):
    id: str
    object: str = "model"
    created: int
    owned_by: str = "company"


class ModelListResponse(BaseModel):
    object: str = "list"
    data: List[ModelObject]
