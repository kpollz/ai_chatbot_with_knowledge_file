# Gauss OpenAI-Compatible Proxy

Proxy server dịch giữa **OpenAI Chat Completions API** (chuẩn) và **Company LLM (Gauss) API** (nội bộ), bao gồm giả lập **function calling** cho LLM chỉ hỗ trợ text thuần.

## Kiến trúc

```
                      OpenAI format                          Company format
┌──────────┐    POST /v1/chat/completions     ┌────────────┐    POST {model-url}     ┌──────────────┐
│ OpenClaw  │ ──────────────────────────────▶  │   Gauss    │ ───────────────────────▶│  Company LLM │
│ (Client)  │ ◀──────────────────────────────  │   Proxy    │ ◀───────────────────────│   (Gauss)    │
└──────────┘    SSE stream / JSON             └────────────┘    JSON / JSON-lines    └──────────────┘
                                               localhost:9000
```

### Proxy thực hiện 4 nhiệm vụ chính

1. **Normalize messages** — chuyển đổi `content` array → string, role `developer` → `system`
2. **Tool injection** — chuyển `tools[]` trong request thành text mô tả, inject vào system prompt
3. **Tool parsing** — phát hiện `<tool_call>` trong response text và chuyển thành OpenAI `tool_calls` format
4. **Format translation** — dịch giữa OpenAI format và Company LLM format (request body, response body, streaming)

## Cấu trúc dự án

```
gauss-openai-proxy/
├── app/
│   ├── main.py               # FastAPI server — endpoints & request pipeline
│   ├── config.py              # Cấu hình, model registry, env vars
│   ├── schemas.py             # Pydantic schemas (request/response OpenAI format)
│   ├── message_normalize.py   # Chuẩn hóa messages (content, role, flatten)
│   ├── tool_translation.py    # Tool calling: OpenAI ↔ text-based <tool_call>
│   └── gauss_client.py        # HTTP client gọi upstream Company LLM
├── API_CONTRACT.md            # Đặc tả API chi tiết
├── requirements.txt           # Python dependencies
├── .env.example               # Mẫu biến môi trường
├── Dockerfile                 # Docker image build
├── docker-compose.yml         # Docker Compose orchestration
└── README.md                  # Tài liệu này
```

## Tính năng

| Tính năng | Mô tả |
|-----------|--------|
| Streaming & Non-streaming | Hỗ trợ cả 2 chế độ SSE stream và JSON response |
| Tool Calling Emulation | Chuyển OpenAI `tools[]` → text prompt; phát hiện `<tool_call>` → OpenAI format |
| Streaming Tool Detection | State machine `StreamingToolDetector` phát hiện tool call trong stream real-time |
| Message Normalization | Xử lý 5 role types: `system`, `developer`, `user`, `assistant`, `tool` |
| Content Array Support | Tự động chuyển `content: [{type: "text", text: "..."}]` → string |
| Model Registry | Hỗ trợ 6 models với legacy name mapping |
| OpenAI Error Format | Trả lỗi đúng chuẩn OpenAI error response |

## Models hỗ trợ

| Model ID | Legacy Name |
|----------|-------------|
| `gauss-2.3` | Gauss2.3 |
| `gauss-2.3-think` | Gauss2.3 Think |
| `gausso-flash` | GaussO Flash |
| `gausso-flash-s` | GaussO Flash (S) |
| `gausso4` | GaussO4 |
| `gausso4-thinking` | GaussO4 Thinking |

## API Endpoints

### `GET /health`

Health check endpoint.

```json
{"status": "ok", "version": "2.0.0", "tool_translation": true}
```

### `GET /v1/models`

Liệt kê các models có sẵn (chuẩn OpenAI).

```json
{
  "object": "list",
  "data": [
    {"id": "gauss-2.3", "object": "model", "created": 1711234567, "owned_by": "company"},
    ...
  ]
}
```

### `POST /v1/chat/completions`

Chat completions endpoint chính (chuẩn OpenAI).

**Request:**

```json
{
  "model": "gauss-2.3",
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Hello!"}
  ],
  "stream": true,
  "temperature": 0.7,
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "search",
        "description": "Search for information",
        "parameters": {
          "type": "object",
          "properties": {
            "query": {"type": "string", "description": "Search query"}
          },
          "required": ["query"]
        }
      }
    }
  ]
}
```

**Response (Non-streaming):**

```json
{
  "id": "chatcmpl-abc123",
  "object": "chat.completion",
  "created": 1711234567,
  "model": "gauss-2.3",
  "choices": [
    {
      "index": 0,
      "message": {"role": "assistant", "content": "Xin chào!"},
      "finish_reason": "stop"
    }
  ],
  "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
}
```

**Response (Streaming — SSE):**

```
data: {"id":"chatcmpl-abc123","object":"chat.completion.chunk","choices":[{"delta":{"role":"assistant","content":"Xin"},"finish_reason":null}]}

data: {"id":"chatcmpl-abc123","object":"chat.completion.chunk","choices":[{"delta":{"content":" chào!"},"finish_reason":null}]}

data: {"id":"chatcmpl-abc123","object":"chat.completion.chunk","choices":[{"delta":{},"finish_reason":"stop"}]}

data: [DONE]
```

**Response (Tool Call — Streaming):**

```
data: {"id":"chatcmpl-abc123","choices":[{"delta":{"role":"assistant","tool_calls":[{"index":0,"id":"call_proxy_abc12345","type":"function","function":{"name":"search","arguments":"{\"query\":\"weather\"}"}}]},"finish_reason":null}]}

data: {"id":"chatcmpl-abc123","choices":[{"delta":{},"finish_reason":"tool_calls"}]}

data: [DONE]
```

## Tool Calling Pipeline

Vì Company LLM (Gauss) chỉ hỗ trợ text thuần, proxy giả lập function calling:

### Request Direction (Client → LLM)

```
1. Client gửi tools[] trong request
2. Proxy chuyển tools[] → text prompt, inject vào system message
3. Assistant messages có tool_calls → chuyển thành text <tool_call>...</tool_call>
4. Tool result messages → chuyển thành text [Tool Result]...[/Tool Result]
```

### Response Direction (LLM → Client)

```
1. LLM trả text có chứa <tool_call>{"name":"...", "arguments":{...}}</tool_call>
2. Proxy phát hiện tag (regex hoặc StreamingToolDetector)
3. Chuyển thành OpenAI tool_calls format trong response
4. finish_reason = "tool_calls" thay vì "stop"
```

## Cài đặt & Chạy

### Yêu cầu

- Python 3.10+
- Kết nối mạng đến Company LLM API

### Cách 1: Chạy trực tiếp với Python

```bash
# Clone và vào thư mục
cd gauss-openai-proxy

# Tạo virtual environment
python -m venv venv
source venv/bin/activate

# Cài dependencies
pip install -r requirements.txt

# Cấu hình
cp .env.example .env
# Sửa .env — điền COMPANY_LLM_API_KEY và cấu hình model registry

# Chạy
cd app
python main.py
```

Server sẽ chạy tại `http://localhost:9000`.

### Cách 2: Chạy bằng Docker Compose (khuyến nghị)

```bash
# Cấu hình
cp .env.example .env
# Sửa .env — điền COMPANY_LLM_API_KEY và cấu hình model registry

# Build và chạy
docker compose up -d

# Xem logs
docker compose logs -f

# Dừng
docker compose down
```

Server sẽ chạy tại `http://localhost:9000`.

## Biến môi trường

| Biến | Mặc định | Mô tả |
|------|----------|--------|
| `PROXY_HOST` | `0.0.0.0` | Host lắng nghe |
| `PROXY_PORT` | `9000` | Port lắng nghe |
| `COMPANY_LLM_API_KEY` | _(bắt buộc)_ | API key xác thực với Company LLM |
| `COMPANY_LLM_MODEL_ID` | _(tùy chọn)_ | Override model-id cho tất cả models |
| `COMPANY_LLM_MODEL_URL` | _(tùy chọn)_ | Override model-url cho tất cả models |
| `DEFAULT_TEMPERATURE` | `0` | Temperature mặc định |
| `DEFAULT_TOP_P` | `0.95` | Top-p mặc định |
| `REQUEST_TIMEOUT` | `60` | Timeout request (giây) |
| `SSL_VERIFY` | `false` | Bật/tắt xác minh SSL |
| `TOOL_CALL_ENABLED` | `true` | Bật/tắt giả lập tool calling |
| `LOG_LEVEL` | `INFO` | Mức log: DEBUG, INFO, WARNING, ERROR |

## Giới hạn của Company LLM (Gauss)

| Khả năng | Hỗ trợ | Ghi chú |
|----------|--------|---------|
| Text generation | Yes | Streaming + non-streaming |
| Function calling (native) | **No** | Proxy giả lập bằng text |
| Vision / Image input | **No** | Chỉ nhận text |
| Reasoning / Thinking | **No** | Không có reasoning tokens |
| Token counting | **No** | Proxy trả `0` cho usage |

## Xử lý lỗi

Proxy trả lỗi theo chuẩn OpenAI:

```json
{
  "error": {
    "message": "Model not found: invalid-model",
    "type": "invalid_request_error",
    "code": "model_not_found"
  }
}
```

| HTTP Status | Nguyên nhân |
|-------------|-------------|
| 401 | Thiếu API key |
| 400 | Request không hợp lệ (không có messages) |
| 404 | Model không tồn tại |
| 502 | Không kết nối được upstream LLM |
| 504 | Upstream LLM timeout |
| 500 | Lỗi upstream khác |

## Tài liệu tham khảo

- [API_CONTRACT.md](API_CONTRACT.md) — Đặc tả API chi tiết, schema, pipeline
