# API Contract: Gauss OpenAI-Compatible Proxy

> Proxy server dịch giữa OpenAI Chat Completions API format và Company LLM (Gauss) API format.
>
> **Trusted source**: Toàn bộ schema trong document này được trích xuất từ code production đã tested:
> - `machine-issue-solver/chatbot/app/company_chat_model.py`
> - `machine-issue-solver/streaming_sample.py`
> - `machine-issue-solver/chatbot/app/config.py`

---

## 1. Tổng quan kiến trúc

```
                      OpenAI format                         Company format
┌──────────┐    POST /v1/chat/completions    ┌────────────┐    POST {model-url}     ┌──────────────┐
│ OpenClaw  │ ─────────────────────────────▶  │   Gauss    │ ───────────────────────▶│  Company LLM │
│ (Client)  │ ◀─────────────────────────────  │   Proxy    │ ◀───────────────────────│   (Gauss)    │
└──────────┘    OpenAI response format       └────────────┘    Company response     └──────────────┘
                                              localhost:9000
```

---

## 2. Proxy Endpoints (Phía OpenClaw gọi vào)

### 2.1 `GET /v1/models` — Liệt kê models

**Response:**
```json
{
  "object": "list",
  "data": [
    {
      "id": "Gauss2.3",
      "object": "model",
      "created": 1700000000,
      "owned_by": "company"
    },
    {
      "id": "Gauss2.3 Think",
      "object": "model",
      "created": 1700000000,
      "owned_by": "company"
    },
    {
      "id": "GaussO Flash",
      "object": "model",
      "created": 1700000000,
      "owned_by": "company"
    },
    {
      "id": "GaussO Flash (S)",
      "object": "model",
      "created": 1700000000,
      "owned_by": "company"
    },
    {
      "id": "GaussO4",
      "object": "model",
      "created": 1700000000,
      "owned_by": "company"
    },
    {
      "id": "GaussO4 Thinking",
      "object": "model",
      "created": 1700000000,
      "owned_by": "company"
    }
  ]
}
```

### 2.2 `POST /v1/chat/completions` — Chat (Non-Streaming)

**Request:**
```json
{
  "model": "Gauss2.3",
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Xin chào"},
    {"role": "assistant", "content": "Chào bạn! Tôi có thể giúp gì?"},
    {"role": "user", "content": "Máy CNC-01 bị lỗi gì?"}
  ],
  "temperature": 0,
  "top_p": 0.95,
  "max_tokens": 4096,
  "stream": false
}
```

**Headers:**
```
Content-Type: application/json
Authorization: Bearer <api-key>
```

**Response (200 OK):**
```json
{
  "id": "chatcmpl-<uuid>",
  "object": "chat.completion",
  "created": 1700000000,
  "model": "Gauss2.3",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Máy CNC-01 có vấn đề về..."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "total_tokens": 0
  }
}
```

> **Lưu ý về `usage`:** Company LLM không trả token counts, nên proxy trả `0` cho tất cả fields.

### 2.3 `POST /v1/chat/completions` — Chat (Streaming)

**Request:** Giống non-streaming, nhưng `"stream": true`.

**Response (200 OK, SSE stream):**

```
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive
```

Mỗi chunk:
```
data: {"id":"chatcmpl-<uuid>","object":"chat.completion.chunk","created":1700000000,"model":"Gauss2.3","choices":[{"index":0,"delta":{"role":"assistant","content":"Máy"},"finish_reason":null}]}

data: {"id":"chatcmpl-<uuid>","object":"chat.completion.chunk","created":1700000000,"model":"Gauss2.3","choices":[{"index":0,"delta":{"content":" CNC"},"finish_reason":null}]}

data: {"id":"chatcmpl-<uuid>","object":"chat.completion.chunk","created":1700000000,"model":"Gauss2.3","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}

data: [DONE]
```

> **Quy tắc SSE:**
> - Chunk đầu tiên có `"delta": {"role": "assistant", "content": "..."}` (có role)
> - Các chunk tiếp theo có `"delta": {"content": "..."}` (chỉ content)
> - Chunk cuối có `"delta": {}` và `"finish_reason": "stop"`
> - Kết thúc bằng `data: [DONE]`

### 2.4 `GET /health` — Health Check

**Response:**
```json
{
  "status": "ok",
  "version": "1.0.0"
}
```

---

## 3. Company LLM API (Phía Proxy gọi đi) — Trích từ production code

### 3.1 Non-Streaming Request

> Source: `company_chat_model.py` lines 154-176, `company_llms_sample_request.py`

```
POST {model-url}?stream=false
```

**Headers:**
```
Content-Type: application/json
x-api-key: <api-key>
```

**Body:**
```json
{
  "component_inputs": {
    "<model-id>": {
      "input_value": "<user_prompt>",
      "max_retries": 3,
      "parameters": "{\"temperature\": 0, \"top_p\": 0.95}",
      "stream": false,
      "system_message": "<system_prompt>"
    }
  }
}
```

**Các trường chi tiết:**

| Field | Type | Mô tả |
|-------|------|--------|
| `component_inputs` | `object` | Dict với key là `model-id` |
| `input_value` | `string` | Nội dung prompt của user (đã ghép từ conversation history) |
| `max_retries` | `int` | `3` cho non-streaming, `0` cho streaming |
| `parameters` | `string` | **JSON string** (không phải object!) chứa temperature, top_p |
| `stream` | `bool` | `false` cho non-streaming |
| `system_message` | `string` | System prompt, có thể rỗng `""` |

### 3.2 Non-Streaming Response

> Source: `company_chat_model.py` lines 88-105, `company_llms_sample_request.py` lines 73-95

```json
{
  "session_id": "<session_id>",
  "outputs": [
    {
      "inputs": {},
      "outputs": [
        {
          "results": {
            "message": {
              "text": "<FORMAT_A hoặc FORMAT_B — xem bên dưới>"
            }
          },
          "timedelta": null,
          "duration": null,
          "component_display_name": "Text Output",
          "component_id": "<component_id>"
        }
      ],
      "legacy_components": [],
      "warning": null
    }
  ]
}
```

**QUAN TRỌNG — `text` field có 2 format:**

**Format A** — `text` là dict (có nested `text` key):
```json
"text": {
  "text": "Câu trả lời của LLM",
  "sender": null,
  "sender_name": null,
  "timestamp": "2025-03-10T...",
  "error": false
}
```

**Format B** — `text` là string trực tiếp:
```json
"text": "Câu trả lời của LLM"
```

**Logic parse (từ `_parse_response`):**
```python
text_field = response['outputs'][0]['outputs'][0]['results']['message']['text']
if isinstance(text_field, dict):
    return text_field['text']    # Format A
return text_field                # Format B
```

### 3.3 Streaming Request

> Source: `company_chat_model.py` lines 109-150, `streaming_sample.py`

```
POST {model-url}?stream=true
```

**Headers:** Giống non-streaming.

**Body:**
```json
{
  "component_inputs": {
    "<model-id>": {
      "input_value": "<user_prompt>",
      "max_retries": 0,
      "parameters": "{\"temperature\": 0, \"top_p\": 0.95, \"extra_body\": {\"repetition_penalty\": 1.05}}",
      "stream": true,
      "system_message": "<system_prompt>"
    }
  }
}
```

**Khác biệt so với non-streaming:**

| Field | Non-Streaming | Streaming |
|-------|---------------|-----------|
| `query param stream` | `"false"` | `"true"` |
| `body stream` | `false` | `true` |
| `max_retries` | `3` | `0` |
| `parameters` | Không có `extra_body` | Có thêm `"extra_body": {"repetition_penalty": 1.05}` |

**HTTP options (bắt buộc cho streaming):**
```python
verify=False          # Bỏ qua SSL verification
proxies={"https": None}  # Không dùng proxy
stream=True           # requests streaming mode
```

### 3.4 Streaming Response

> Source: `streaming_sample.py`, `company_chat_model.py` lines 133-148

Response là dòng JSON, mỗi dòng là một JSON object hoàn chỉnh (**không phải SSE format**):

```
{"event": "token", "data": {"chunk": "Máy"}}
{"event": "token", "data": {"chunk": " CNC"}}
{"event": "token", "data": {"chunk": "-01"}}
{"event": "token", "data": {"chunk": " có"}}
```

**Cấu trúc mỗi dòng:**
```json
{
  "event": "token",
  "data": {
    "chunk": "<text_chunk>"
  }
}
```

**Quy tắc parse (từ production code):**
1. Bỏ qua dòng rỗng (`if not line: continue`)
2. Decode UTF-8 và parse JSON
3. Chỉ xử lý khi `event == "token"`
4. Lấy text từ `data.chunk`
5. Bỏ qua nếu chunk rỗng hoặc JSON malformed

---

## 4. Translation Mapping

### 4.1 Request Translation (OpenAI → Company)

```
OpenAI Request                          Company Request
─────────────────                       ──────────────────
Authorization: Bearer <key>       →     x-api-key: <key>

model: "Gauss2.3"                 →     Lookup model-id & model-url từ COMPANY_MODELS registry

messages: [                       →     system_message: <content từ role=system>
  {role: "system", content: ...}        input_value: <ghép tất cả messages còn lại>
  {role: "user", content: ...}
  {role: "assistant", content: ...}
  {role: "user", content: ...}
]

temperature: 0                    →     parameters: '{"temperature": 0, "top_p": 0.95}'
top_p: 0.95

stream: true/false                →     stream: true/false (cả query param và body)
                                        max_retries: 0 (stream) / 3 (non-stream)
```

### 4.2 Messages Flattening Logic

> Nguồn gốc: `company_chat_model.py` `_parse_messages()` lines 73-86
>
> Company LLM chỉ nhận 2 fields: `system_message` (string) và `input_value` (string).
> Phải flatten multi-turn conversation thành 1 string.

**Quy tắc:**

```
Input (OpenAI messages):
[
  {"role": "system", "content": "Bạn là trợ lý."},
  {"role": "user", "content": "Xin chào"},
  {"role": "assistant", "content": "Chào bạn!"},
  {"role": "user", "content": "Máy CNC lỗi gì?"}
]

Output:
  system_message = "Bạn là trợ lý."
  input_value = (xem các strategy bên dưới)
```

**Strategy: Formatted conversation** (khuyến nghị — giữ nguyên context multi-turn):
```
input_value = """User: Xin chào
Assistant: Chào bạn!
User: Máy CNC lỗi gì?"""
```

**Edge cases:**
- Nhiều system messages → lấy message **cuối cùng** (theo behavior của `_parse_messages`)
- Không có system message → `system_message = ""`
- Không có user message → trả lỗi 400
- Chỉ có 1 user message → dùng trực tiếp, không cần format prefix

### 4.3 Response Translation (Company → OpenAI)

**Non-Streaming:**
```
Company Response                        OpenAI Response
─────────────────                       ──────────────────
outputs[0]                              choices[0]
  .outputs[0]                             .message
    .results.message.text      →            .content
    (dict → .text.text)                   .role = "assistant"
    (string → dùng trực tiếp)           .finish_reason = "stop"

                                        id = "chatcmpl-<uuid>"
                                        object = "chat.completion"
                                        model = <model từ request>
                                        usage = {prompt_tokens: 0, ...}
```

**Streaming:**
```
Company streaming line                  OpenAI SSE chunk
─────────────────────                   ─────────────────
{"event":"token",              →        data: {"id":"chatcmpl-<uuid>",
 "data":{"chunk":"text"}}               "object":"chat.completion.chunk",
                                         "choices":[{"index":0,
                                           "delta":{"content":"text"},
                                           "finish_reason":null}]}

(stream kết thúc)              →        data: {"choices":[{"delta":{},
                                           "finish_reason":"stop"}]}
                                        data: [DONE]
```

---

## 5. Model Registry

> Source: `config.py` lines 31-56

| Model Name | model-id | model-url | Ghi chú |
|------------|----------|-----------|---------|
| Gauss2.3 | `model-id` | `https://mycompany.com/api/v1/run/session_id` | Model mặc định |
| Gauss2.3 Think | `model-id` | `https://mycompany.com/api/v1/run/session_id` | Thinking variant |
| GaussO Flash | `model-id` | `https://mycompany.com/api/v1/run/session_id` | Nhanh |
| GaussO Flash (S) | `model-id` | `https://mycompany.com/api/v1/run/session_id` | Nhỏ hơn |
| GaussO4 | `model-id` | `https://mycompany.com/api/v1/run/session_id` | Mạnh nhất |
| GaussO4 Thinking | `model-id` | `https://mycompany.com/api/v1/run/session_id` | Thinking + mạnh |

> **Lưu ý:** `model-id` và `model-url` trong bảng trên là placeholder. Giá trị thực được cấu hình qua:
> - Environment variables: `COMPANY_LLM_MODEL_ID`, `COMPANY_LLM_MODEL_URL` (override toàn bộ)
> - Hoặc hardcoded trong `COMPANY_MODELS` dict (sẽ copy sang proxy config)

---

## 6. Error Handling

### 6.1 Proxy → Client (OpenAI format errors)

| HTTP Status | Khi nào | Response body |
|-------------|---------|---------------|
| 400 | Thiếu messages, model không hợp lệ | `{"error": {"message": "...", "type": "invalid_request_error", "code": null}}` |
| 401 | Thiếu/sai API key | `{"error": {"message": "Invalid API key", "type": "authentication_error", "code": null}}` |
| 404 | Model không tồn tại trong registry | `{"error": {"message": "Model not found: ...", "type": "invalid_request_error", "code": "model_not_found"}}` |
| 500 | Company LLM trả lỗi hoặc không parse được | `{"error": {"message": "...", "type": "server_error", "code": null}}` |
| 502 | Không kết nối được Company LLM | `{"error": {"message": "Failed to connect to upstream LLM", "type": "server_error", "code": null}}` |
| 504 | Company LLM timeout | `{"error": {"message": "Upstream LLM timeout", "type": "server_error", "code": null}}` |

### 6.2 Streaming Error Handling

Nếu lỗi xảy ra **giữa stream**:
```
data: {"id":"chatcmpl-...","object":"chat.completion.chunk","choices":[{"index":0,"delta":{},"finish_reason":"error"}]}

data: [DONE]
```

Nếu lỗi xảy ra **trước khi stream bắt đầu**: trả HTTP error bình thường (không phải SSE).

---

## 7. Configuration (Environment Variables)

| Variable | Mặc định | Mô tả |
|----------|----------|-------|
| `PROXY_HOST` | `0.0.0.0` | Host bind |
| `PROXY_PORT` | `9000` | Port |
| `COMPANY_LLM_API_KEY` | (bắt buộc) | API key cho Company LLM |
| `COMPANY_LLM_MODEL_ID` | `null` | Override model-id cho tất cả models |
| `COMPANY_LLM_MODEL_URL` | `null` | Override model-url cho tất cả models |
| `DEFAULT_TEMPERATURE` | `0` | Temperature mặc định |
| `DEFAULT_TOP_P` | `0.95` | Top-p mặc định |
| `REQUEST_TIMEOUT` | `60` | Timeout gọi Company LLM (giây) |
| `SSL_VERIFY` | `false` | Verify SSL khi gọi Company LLM |
| `LOG_LEVEL` | `INFO` | Log level |

---

## 8. Ví dụ End-to-End

### 8.1 Non-Streaming

**Client gửi đến Proxy:**
```bash
curl -X POST http://localhost:9000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer my-api-key" \
  -d '{
    "model": "Gauss2.3",
    "messages": [
      {"role": "system", "content": "Bạn là trợ lý nhà máy."},
      {"role": "user", "content": "Máy CNC-01 bị lỗi gì?"}
    ],
    "temperature": 0,
    "stream": false
  }'
```

**Proxy dịch và gửi đến Company LLM:**
```bash
POST https://mycompany.com/api/v1/run/session_id?stream=false
x-api-key: my-api-key

{
  "component_inputs": {
    "model-id": {
      "input_value": "Máy CNC-01 bị lỗi gì?",
      "max_retries": 3,
      "parameters": "{\"temperature\": 0, \"top_p\": 0.95}",
      "stream": false,
      "system_message": "Bạn là trợ lý nhà máy."
    }
  }
}
```

**Company LLM trả về:**
```json
{
  "session_id": "abc123",
  "outputs": [{
    "inputs": {},
    "outputs": [{
      "results": {
        "message": {
          "text": {
            "text": "Máy CNC-01 đang gặp vấn đề quá nhiệt...",
            "sender": null,
            "sender_name": null,
            "timestamp": "2025-03-10T10:00:00",
            "error": false
          }
        }
      },
      "timedelta": null,
      "duration": null,
      "component_display_name": "Text Output",
      "component_id": "comp-xyz"
    }],
    "legacy_components": [],
    "warning": null
  }]
}
```

**Proxy dịch và trả về Client:**
```json
{
  "id": "chatcmpl-f47ac10b-58cc",
  "object": "chat.completion",
  "created": 1710057600,
  "model": "Gauss2.3",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Máy CNC-01 đang gặp vấn đề quá nhiệt..."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "total_tokens": 0
  }
}
```

### 8.2 Streaming

**Client gửi đến Proxy:**
```bash
curl -X POST http://localhost:9000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer my-api-key" \
  -d '{
    "model": "Gauss2.3",
    "messages": [
      {"role": "user", "content": "Hello"}
    ],
    "stream": true
  }'
```

**Proxy dịch và gửi đến Company LLM:**
```bash
POST https://mycompany.com/api/v1/run/session_id?stream=true
x-api-key: my-api-key
# HTTP stream=True, verify=False, proxies={"https": None}

{
  "component_inputs": {
    "model-id": {
      "input_value": "Hello",
      "max_retries": 0,
      "parameters": "{\"temperature\": 0, \"top_p\": 0.95, \"extra_body\": {\"repetition_penalty\": 1.05}}",
      "stream": true,
      "system_message": ""
    }
  }
}
```

**Company LLM stream (mỗi dòng là JSON):**
```
{"event": "token", "data": {"chunk": "Xin"}}
{"event": "token", "data": {"chunk": " chào"}}
{"event": "token", "data": {"chunk": "!"}}
```

**Proxy dịch thành SSE và trả về Client:**
```
data: {"id":"chatcmpl-f47ac10b-58cc","object":"chat.completion.chunk","created":1710057600,"model":"Gauss2.3","choices":[{"index":0,"delta":{"role":"assistant","content":"Xin"},"finish_reason":null}]}

data: {"id":"chatcmpl-f47ac10b-58cc","object":"chat.completion.chunk","created":1710057600,"model":"Gauss2.3","choices":[{"index":0,"delta":{"content":" chào"},"finish_reason":null}]}

data: {"id":"chatcmpl-f47ac10b-58cc","object":"chat.completion.chunk","created":1710057600,"model":"Gauss2.3","choices":[{"index":0,"delta":{"content":"!"},"finish_reason":null}]}

data: {"id":"chatcmpl-f47ac10b-58cc","object":"chat.completion.chunk","created":1710057600,"model":"Gauss2.3","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}

data: [DONE]
```
