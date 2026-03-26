# API Contract: Gauss OpenAI-Compatible Proxy

> Proxy server dịch giữa OpenAI Chat Completions API format và Company LLM (Gauss) API format.
>
> **Trusted sources**:
> - **Phía OpenClaw (client)**: `@mariozechner/pi-ai@0.57.1` — file `dist/providers/openai-completions.js`, hàm `buildParams()` (dòng 295-356) và `convertMessages()` (dòng 388-603)
> - **Phía Company LLM (upstream)**: `machine-issue-solver/chatbot/app/company_chat_model.py`, `machine-issue-solver/streaming_sample.py`
> - **OpenClaw config**: `deploy/openclaw.json` — provider `gauss` với `api: "openai-completions"`

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

## 2. Schema thực tế OpenClaw gửi đến Proxy (Request)

> Source: `@mariozechner/pi-ai` — `openai-completions.js` hàm `buildParams()` + `convertMessages()`
>
> OpenClaw dùng thư viện `openai` (Node.js SDK) nên tuân theo chuẩn OpenAI Chat Completions API đầy đủ,
> không phải bản rút gọn. Proxy cần handle đúng format này.

### 2.1 Request Body Schema

```jsonc
// POST /v1/chat/completions
{
  // ── Bắt buộc ──────────────────────────────────────────────────────────
  "model": "gauss-2.3",              // string — model ID từ OpenClaw config
  "messages": [ /* xem 2.2 */ ],     // array — danh sách messages
  "stream": true,                    // boolean — OpenClaw luôn gửi true (streaming)

  // ── Tùy chọn (OpenClaw có thể gửi hoặc không) ────────────────────────
  "temperature": 0.7,                // float | undefined
  "max_completion_tokens": 8192,     // int | undefined — KHÔNG phải max_tokens!
  "stream_options": {                // object | undefined
    "include_usage": true
  },
  "store": false,                    // boolean | undefined
  "tools": [ /* xem 2.3 */ ],       // array | undefined — tool definitions
  "tool_choice": "auto",            // string | object | undefined
  "reasoning_effort": "medium",      // string | undefined — cho reasoning models
  "enable_thinking": true            // boolean | undefined — cho Z.AI/Qwen models
}
```

> **Lưu ý quan trọng:**
> - OpenClaw gửi `max_completion_tokens` (OpenAI mới), KHÔNG phải `max_tokens` (OpenAI cũ)
> - `stream` luôn là `true` — OpenClaw chỉ dùng streaming mode
> - Proxy nên dùng Pydantic `model_config = ConfigDict(extra="ignore")` để bỏ qua các field không cần thiết

### 2.2 Messages Schema

OpenClaw gửi messages theo chuẩn OpenAI đầy đủ. Có **5 loại role** và `content` có thể là **string HOẶC array**.

#### Role: `"system"` hoặc `"developer"`

```jsonc
{
  "role": "system",       // "system" cho non-reasoning models
  // "role": "developer", // "developer" cho reasoning models (gauss-2.3-think, gausso4, gausso4-thinking)
  "content": "You are a helpful assistant."  // luôn là string
}
```

> **Khi nào dùng "developer"?**
> OpenClaw gửi `"developer"` thay vì `"system"` khi model config có `reasoning: true` VÀ provider
> được detect là hỗ trợ developer role. Provider "gauss" KHÔNG nằm trong danh sách non-standard
> nên `supportsDeveloperRole = true` → reasoning models sẽ gửi `"developer"`.

#### Role: `"user"` — Content dạng string (hiếm gặp, chỉ khi message đơn giản)

```json
{
  "role": "user",
  "content": "Xin chào"
}
```

#### Role: `"user"` — Content dạng array (TRƯỜNG HỢP PHỔ BIẾN NHẤT)

```json
{
  "role": "user",
  "content": [
    {
      "type": "text",
      "text": "Máy CNC-01 bị lỗi gì?"
    }
  ]
}
```

Nếu có hình ảnh (model config `input` chứa `"image"`):
```json
{
  "role": "user",
  "content": [
    {"type": "text", "text": "Hình này là gì?"},
    {"type": "image_url", "image_url": {"url": "data:image/png;base64,iVBOR..."}}
  ]
}
```

> **Gauss models chỉ hỗ trợ text** (`input: ["text"]`) nên sẽ không có image_url,
> nhưng proxy vẫn nên handle gracefully.

#### Role: `"assistant"` — Content dạng array

```jsonc
{
  "role": "assistant",
  "content": [
    {"type": "text", "text": "Máy CNC-01 đang gặp vấn đề quá nhiệt..."}
  ],
  // Các field tùy chọn (khi agent dùng tools):
  "tool_calls": [
    {
      "id": "call_abc123",
      "type": "function",
      "function": {
        "name": "search_docs",
        "arguments": "{\"query\": \"CNC-01 error\"}"
      }
    }
  ],
  "reasoning_details": [...]  // hiếm gặp, cho encrypted reasoning
}
```

> **`content` của assistant luôn là array** `[{type: "text", text: "..."}]`, KHÔNG bao giờ là string đơn
> (trừ trường hợp provider github-copilot, không liên quan ở đây).

#### Role: `"tool"` — Tool result (khi agent dùng tools)

```json
{
  "role": "tool",
  "content": "Kết quả tra cứu: CNC-01 lỗi E-STOP...",
  "tool_call_id": "call_abc123"
}
```

### 2.3 Tools Schema (tùy chọn)

```json
{
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "search_docs",
        "description": "Search documentation for machine errors",
        "parameters": {
          "type": "object",
          "properties": {
            "query": {"type": "string"}
          },
          "required": ["query"]
        },
        "strict": false
      }
    }
  ]
}
```

### 2.4 Headers

```
Content-Type: application/json
Authorization: Bearer <GAUSS_API_KEY>
```

> OpenClaw dùng thư viện `openai` SDK nên tự thêm các header khác như `User-Agent`, `OpenAI-Organization`, v.v.
> Proxy chỉ cần quan tâm `Authorization`.

---

## 3. Schema thực tế OpenClaw mong đợi nhận (Response)

### 3.1 Non-Streaming Response (200 OK)

```json
{
  "id": "chatcmpl-<uuid>",
  "object": "chat.completion",
  "created": 1700000000,
  "model": "gauss-2.3",
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

> OpenClaw đọc thêm (nếu có):
> - `usage.prompt_tokens_details.cached_tokens`
> - `usage.completion_tokens_details.reasoning_tokens`
>
> Proxy không cần trả các field này, giá trị `0` là đủ.

### 3.2 Streaming Response (200 OK, SSE)

**Headers:**
```
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive
```

**Chunk đầu tiên** (có `role`):
```
data: {"id":"chatcmpl-<uuid>","object":"chat.completion.chunk","created":1700000000,"model":"gauss-2.3","choices":[{"index":0,"delta":{"role":"assistant","content":"Máy"},"finish_reason":null}]}

```

**Các chunk tiếp theo** (chỉ `content`):
```
data: {"id":"chatcmpl-<uuid>","object":"chat.completion.chunk","created":1700000000,"model":"gauss-2.3","choices":[{"index":0,"delta":{"content":" CNC"},"finish_reason":null}]}

```

**Chunk cuối** (`finish_reason: "stop"`):
```
data: {"id":"chatcmpl-<uuid>","object":"chat.completion.chunk","created":1700000000,"model":"gauss-2.3","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}

```

**Kết thúc:**
```
data: [DONE]

```

> **Quy tắc SSE:**
> - Chunk đầu tiên: `delta` có `role` + `content`
> - Các chunk tiếp: `delta` chỉ có `content`
> - Chunk cuối: `delta` rỗng `{}`, `finish_reason: "stop"`
> - Kết thúc bằng `data: [DONE]`
> - Mỗi chunk cách nhau bởi 2 newlines (`\n\n`)

### 3.3 Error Response

```json
{
  "error": {
    "message": "Model not found: unknown-model",
    "type": "invalid_request_error",
    "code": "model_not_found"
  }
}
```

---

## 4. Mismatch Analysis: Proxy hiện tại vs OpenClaw thực tế

> Phần này liệt kê các điểm mà proxy code hiện tại (`schemas.py`) chưa khớp với request thực tế từ OpenClaw.

### 4.1 Gây lỗi 422 (Pydantic validation fail)

| # | Vấn đề | OpenClaw gửi | Proxy mong đợi | Giải pháp |
|---|--------|-------------|-----------------|-----------|
| 1 | **`content` user message** | `[{type: "text", text: "..."}]` (array) | `content: str` | Thêm validator normalize array → string |
| 2 | **`content` assistant message** | `[{type: "text", text: "..."}]` (array) | `content: str` | Thêm validator normalize array → string |
| 3 | **`role: "developer"`** | Gửi cho reasoning models | Không có trong schema | Thêm vào danh sách roles hợp lệ, xử lý như `"system"` |
| 4 | **`role: "tool"` message** | `{role: "tool", content: "...", tool_call_id: "..."}` | Schema không có `tool_call_id` field | Thêm field tùy chọn hoặc skip message này |

### 4.2 Không gây 422 nhưng proxy mất thông tin (Pydantic ignore extra fields)

| # | Field | OpenClaw gửi | Proxy hiện tại |
|---|-------|-------------|----------------|
| 5 | `max_completion_tokens` | number | Chỉ có `max_tokens` — giá trị bị mất |
| 6 | `stream_options` | `{include_usage: true}` | Không có — bị bỏ qua |
| 7 | `store` | `false` | Không có — bị bỏ qua |
| 8 | `tools` | Array of tool defs | Không có — bị bỏ qua |
| 9 | `tool_choice` | string/object | Không có — bị bỏ qua |
| 10 | `reasoning_effort` | string | Không có — bị bỏ qua |
| 11 | `tool_calls` trên assistant | Array | Không có — bị bỏ qua |

> **Ưu tiên fix:** #1 và #2 là nguyên nhân chính gây 422. #3 và #4 có thể gây lỗi logic.
> #5-#11 ít quan trọng vì Company LLM không hỗ trợ tools/reasoning nên bỏ qua là hợp lý.

---

## 5. Proxy Endpoints

### 5.1 `GET /health` — Health Check

**Response:**
```json
{
  "status": "ok",
  "version": "1.0.0"
}
```

### 5.2 `GET /v1/models` — Liệt kê models

**Response:**
```json
{
  "object": "list",
  "data": [
    {"id": "gauss-2.3", "object": "model", "created": 1700000000, "owned_by": "company"},
    {"id": "gauss-2.3-think", "object": "model", "created": 1700000000, "owned_by": "company"},
    {"id": "gausso-flash", "object": "model", "created": 1700000000, "owned_by": "company"},
    {"id": "gausso-flash-s", "object": "model", "created": 1700000000, "owned_by": "company"},
    {"id": "gausso4", "object": "model", "created": 1700000000, "owned_by": "company"},
    {"id": "gausso4-thinking", "object": "model", "created": 1700000000, "owned_by": "company"}
  ]
}
```

### 5.3 `POST /v1/chat/completions` — Chat Completions

Xem Section 2 (Request) và Section 3 (Response) ở trên.

---

## 6. Company LLM API (Phía Proxy gọi đi) — Trích từ production code

### 6.1 Non-Streaming Request

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

### 6.2 Non-Streaming Response

> Source: `company_chat_model.py` lines 88-105

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
              "text": "<FORMAT_A hoặc FORMAT_B>"
            }
          }
        }
      ]
    }
  ]
}
```

**`text` field có 2 format:**

**Format A** — `text` là dict:
```json
"text": {
  "text": "Câu trả lời của LLM",
  "sender": null,
  "sender_name": null,
  "timestamp": "2025-03-10T...",
  "error": false
}
```

**Format B** — `text` là string:
```json
"text": "Câu trả lời của LLM"
```

### 6.3 Streaming Request

```
POST {model-url}?stream=true
```

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

### 6.4 Streaming Response

Response là dòng JSON, mỗi dòng là một JSON object hoàn chỉnh (**không phải SSE format**):

```
{"event": "token", "data": {"chunk": "Máy"}}
{"event": "token", "data": {"chunk": " CNC"}}
{"event": "token", "data": {"chunk": "-01"}}
```

---

## 7. Translation Mapping

### 7.1 Request Translation (OpenAI → Company)

```
OpenAI Request (từ OpenClaw)               Company Request
─────────────────────────────               ──────────────────
Authorization: Bearer <key>          →      x-api-key: <key>

model: "gauss-2.3"                   →      Lookup model-id & model-url từ registry

messages: [                          →      system_message: <text từ system/developer role>
  {role: "system"|"developer",              input_value: <ghép tất cả non-system messages>
   content: "..."},
  {role: "user",
   content: [{type:"text",text:"..."}]},    ← CẦN NORMALIZE content array → string!
  {role: "assistant",
   content: [{type:"text",text:"..."}]},    ← CẦN NORMALIZE content array → string!
  {role: "tool",                            ← BỎ QUA (Company LLM không hỗ trợ tools)
   content: "...",
   tool_call_id: "..."}
]

temperature: 0.7                     →      parameters: '{"temperature": 0.7, "top_p": 0.95}'
max_completion_tokens: 8192          →      (bỏ qua — Company LLM tự quản lý)
stream: true                         →      stream: true (cả query param và body)
                                            max_retries: 0 (stream) / 3 (non-stream)

stream_options, store, tools,        →      (bỏ qua — không liên quan đến Company LLM)
tool_choice, reasoning_effort
```

### 7.2 Messages Flattening Logic

> Company LLM chỉ nhận 2 fields: `system_message` (string) và `input_value` (string).
> Phải flatten multi-turn conversation thành 1 string.

**Quy tắc normalize `content`:**
```
Nếu content là string   → dùng trực tiếp
Nếu content là array    → ghép text từ các item có type="text"
                           Bỏ qua type="image_url" và các type khác
```

**Quy tắc flatten messages:**
```
Input (đã normalize):
  role: "system"/"developer"  → system_message (lấy message cuối cùng)
  role: "user"                → ghép vào input_value
  role: "assistant"           → ghép vào input_value
  role: "tool"                → bỏ qua hoặc ghép vào input_value

Output:
  system_message = "Bạn là trợ lý."
  input_value = "User: Xin chào\nAssistant: Chào bạn!\nUser: Máy CNC lỗi gì?"
```

**Edge cases:**
- Nhiều system/developer messages → lấy message **cuối cùng**
- Không có system message → `system_message = ""`
- Không có user message → trả lỗi 400
- Chỉ có 1 user message → dùng trực tiếp, không cần format prefix

### 7.3 Response Translation (Company → OpenAI)

**Non-Streaming:**
```
Company Response                        OpenAI Response
─────────────────                       ──────────────────
outputs[0]                              choices[0]
  .outputs[0]                             .message
    .results.message.text      →            .content (string)
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

## 8. Model Registry

| Model Name (OpenClaw config) | Model ID | Reasoning? | Ghi chú |
|------------------------------|----------|------------|---------|
| Gauss 2.3 | `gauss-2.3` | No | Model mặc định, system role = "system" |
| Gauss 2.3 Think | `gauss-2.3-think` | Yes | system role = "developer" |
| GaussO Flash | `gausso-flash` | No | system role = "system" |
| GaussO Flash (S) | `gausso-flash-s` | No | system role = "system" |
| GaussO4 | `gausso4` | Yes | system role = "developer" |
| GaussO4 Thinking | `gausso4-thinking` | Yes | system role = "developer" |

> Model IDs ở đây là từ `deploy/openclaw.json`. Proxy cần map sang `model-id` + `model-url` nội bộ.
> Cấu hình qua env vars `COMPANY_LLM_MODEL_ID`, `COMPANY_LLM_MODEL_URL` (override toàn bộ)
> hoặc hardcoded trong `COMPANY_MODELS` dict.

---

## 9. Error Handling

### 9.1 Proxy → Client (OpenAI format errors)

| HTTP Status | Khi nào | Response body |
|-------------|---------|---------------|
| 400 | Thiếu messages, model không hợp lệ | `{"error": {"message": "...", "type": "invalid_request_error", "code": null}}` |
| 401 | Thiếu/sai API key | `{"error": {"message": "...", "type": "authentication_error", "code": null}}` |
| 404 | Model không tồn tại trong registry | `{"error": {"message": "Model not found: ...", "type": "invalid_request_error", "code": "model_not_found"}}` |
| 422 | Request body không hợp lệ (Pydantic) | `{"detail": [{"loc": [...], "msg": "...", "type": "..."}]}` |
| 500 | Company LLM trả lỗi hoặc không parse được | `{"error": {"message": "...", "type": "server_error", "code": null}}` |
| 502 | Không kết nối được Company LLM | `{"error": {"message": "Failed to connect to upstream LLM", "type": "server_error", "code": null}}` |
| 504 | Company LLM timeout | `{"error": {"message": "Upstream LLM timeout", "type": "server_error", "code": null}}` |

### 9.2 Streaming Error Handling

Nếu lỗi xảy ra **giữa stream**:
```
data: {"id":"chatcmpl-...","object":"chat.completion.chunk","choices":[{"index":0,"delta":{},"finish_reason":"error"}]}

data: [DONE]
```

---

## 10. Configuration (Environment Variables)

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

## 11. Ví dụ End-to-End

### 11.1 Non-Streaming (đơn giản nhất)

**Client gửi đến Proxy:**
```bash
curl -X POST http://localhost:9000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer my-api-key" \
  -d '{
    "model": "gauss-2.3",
    "messages": [
      {"role": "system", "content": "Bạn là trợ lý nhà máy."},
      {"role": "user", "content": "Máy CNC-01 bị lỗi gì?"}
    ],
    "temperature": 0,
    "stream": false
  }'
```

**Proxy dịch và gửi đến Company LLM:**
```
POST https://mycompany.com/api/v1/run/session_id?stream=false
x-api-key: my-api-key
```
```json
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

**Proxy trả về Client:**
```json
{
  "id": "chatcmpl-f47ac10b58cc",
  "object": "chat.completion",
  "created": 1710057600,
  "model": "gauss-2.3",
  "choices": [
    {
      "index": 0,
      "message": {"role": "assistant", "content": "Máy CNC-01 đang gặp vấn đề quá nhiệt..."},
      "finish_reason": "stop"
    }
  ],
  "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
}
```

### 11.2 Streaming — Format thực tế từ OpenClaw (content dạng array)

**OpenClaw gửi đến Proxy (đây là format THỰC TẾ, không phải format đơn giản):**
```json
{
  "model": "gauss-2.3",
  "messages": [
    {"role": "system", "content": "Bạn là trợ lý nhà máy."},
    {"role": "user", "content": [{"type": "text", "text": "Xin chào"}]},
    {"role": "assistant", "content": [{"type": "text", "text": "Chào bạn!"}]},
    {"role": "user", "content": [{"type": "text", "text": "Máy CNC-01 bị lỗi gì?"}]}
  ],
  "stream": true,
  "stream_options": {"include_usage": true},
  "store": false,
  "max_completion_tokens": 8192,
  "temperature": 0
}
```

**Proxy cần normalize messages rồi gửi đến Company LLM:**
```
POST https://mycompany.com/api/v1/run/session_id?stream=true
x-api-key: my-api-key
```
```json
{
  "component_inputs": {
    "model-id": {
      "input_value": "User: Xin chào\nAssistant: Chào bạn!\nUser: Máy CNC-01 bị lỗi gì?",
      "max_retries": 0,
      "parameters": "{\"temperature\": 0, \"top_p\": 0.95, \"extra_body\": {\"repetition_penalty\": 1.05}}",
      "stream": true,
      "system_message": "Bạn là trợ lý nhà máy."
    }
  }
}
```

**Proxy trả về SSE stream:**
```
data: {"id":"chatcmpl-f47ac10b58cc","object":"chat.completion.chunk","created":1710057600,"model":"gauss-2.3","choices":[{"index":0,"delta":{"role":"assistant","content":"Máy"},"finish_reason":null}]}

data: {"id":"chatcmpl-f47ac10b58cc","object":"chat.completion.chunk","created":1710057600,"model":"gauss-2.3","choices":[{"index":0,"delta":{"content":" CNC-01"},"finish_reason":null}]}

data: {"id":"chatcmpl-f47ac10b58cc","object":"chat.completion.chunk","created":1710057600,"model":"gauss-2.3","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}

data: [DONE]
```

### 11.3 Streaming — Reasoning model với developer role

**OpenClaw gửi đến Proxy:**
```json
{
  "model": "gausso4",
  "messages": [
    {"role": "developer", "content": "Bạn là chuyên gia bảo trì máy."},
    {"role": "user", "content": [{"type": "text", "text": "Phân tích lỗi máy CNC-01"}]}
  ],
  "stream": true,
  "stream_options": {"include_usage": true},
  "store": false,
  "max_completion_tokens": 8192,
  "reasoning_effort": "medium"
}
```

> Proxy cần xử lý `role: "developer"` giống như `role: "system"`.
