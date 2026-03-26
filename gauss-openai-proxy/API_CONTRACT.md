# API Contract: Gauss OpenAI-Compatible Proxy

> Proxy server dịch giữa **OpenAI Chat Completions API** (chuẩn) và **Company LLM (Gauss) API** (nội bộ).
>
> Proxy không chỉ dịch format, mà còn **giả lập function calling** cho LLM chỉ hỗ trợ text thuần.
>
> **Trusted sources**:
> - **OpenClaw (client)**: thư viện `@mariozechner/pi-ai@0.57.1` — file `dist/providers/openai-completions.js`
> - **Company LLM (upstream)**: `machine-issue-solver/chatbot/app/company_chat_model.py`
> - **Tool calling reference**: `machine-issue-solver/chatbot/app/graph.py` — ReAct agent pattern

---

## 1. Tổng quan kiến trúc

```
                      OpenAI format                          Company format
┌──────────┐    POST /v1/chat/completions     ┌────────────┐    POST {model-url}     ┌──────────────┐
│ OpenClaw  │ ──────────────────────────────▶  │   Gauss    │ ───────────────────────▶│  Company LLM │
│ (Client)  │ ◀──────────────────────────────  │   Proxy    │ ◀───────────────────────│   (Gauss)    │
└──────────┘    SSE stream / JSON             └────────────┘    JSON / JSON-lines    └──────────────┘
                                               localhost:9000
```

### 1.1 Vai trò của Proxy

Proxy thực hiện **4 nhiệm vụ chính**:

1. **Normalize messages**: chuyển đổi content array → string, `developer` → `system`, v.v.
2. **Tool injection**: chuyển `tools[]` trong request thành text mô tả tool inject vào system prompt
3. **Tool parsing**: phát hiện `<tool_call>` trong response text của Gauss và chuyển thành SSE `tool_calls` chuẩn OpenAI
4. **Format translation**: dịch giữa OpenAI format và Company LLM format (request body, response body, streaming)

### 1.2 Giới hạn của Company LLM (Gauss)

| Khả năng | Hỗ trợ? | Ghi chú |
|----------|---------|---------|
| Text generation | Yes | Streaming + non-streaming |
| Function calling (native) | **No** | Chỉ trả text thuần |
| Vision / Image input | **No** | Chỉ nhận text |
| Reasoning / Thinking | **No** | Không có reasoning tokens |
| Token counting | **No** | Proxy trả `0` cho usage |

---

## 2. Request: OpenClaw gửi đến Proxy

> Source: `openai-completions.js` hàm `buildParams()` (dòng 295-356) và `convertMessages()` (dòng 388-603)

### 2.1 HTTP Request

```
POST /v1/chat/completions HTTP/1.1
Host: localhost:9000
Content-Type: application/json
Authorization: Bearer <GAUSS_API_KEY>
```

### 2.2 Request Body — Schema đầy đủ

```jsonc
{
  // ── Bắt buộc ──────────────────────────────────────────────────────────────
  "model": "gauss-2.3",                     // string — model ID
  "messages": [ /* xem 2.3 */ ],            // array — danh sách messages
  "stream": true,                           // boolean — OpenClaw luôn gửi true

  // ── Tùy chọn — Proxy nên CHẤP NHẬN và XỬ LÝ ────────────────────────────
  "temperature": 0.7,                       // float — truyền xuống Gauss
  "max_completion_tokens": 8192,            // int — OpenAI mới, thay cho max_tokens
  "max_tokens": 4096,                       // int — OpenAI cũ (hiếm gặp từ OpenClaw)

  // ── Tùy chọn — Proxy nên CHẤP NHẬN nhưng BỎ QUA (Gauss không hỗ trợ) ───
  "stream_options": {"include_usage": true}, // object
  "store": false,                            // boolean
  "tools": [ /* xem 2.4 */ ],               // array — CẦN CHUYỂN THÀNH TEXT PROMPT
  "tool_choice": "auto",                    // string | object
  "reasoning_effort": "medium",             // string
  "enable_thinking": true,                  // boolean
  "top_p": 0.95,                            // float — truyền xuống Gauss
  "parallel_tool_calls": true               // boolean
}
```

> **Nguyên tắc**: Pydantic schema dùng `model_config = ConfigDict(extra="ignore")` để bỏ qua
> các field không biết. Chỉ extract các field cần thiết.

### 2.3 Messages — Tất cả các loại role

OpenClaw gửi **5 loại role**. Proxy cần xử lý từng loại.

#### 2.3.1 `role: "system"` — System prompt (non-reasoning models)

```json
{"role": "system", "content": "You are a helpful assistant."}
```

- `content` luôn là **string**
- Dùng cho non-reasoning models: `gauss-2.3`, `gausso-flash`, `gausso-flash-s`

#### 2.3.2 `role: "developer"` — System prompt (reasoning models)

```json
{"role": "developer", "content": "You are a helpful assistant."}
```

- Giống `system` nhưng gửi cho reasoning models: `gauss-2.3-think`, `gausso4`, `gausso4-thinking`
- **Proxy xử lý**: coi như `system` (Gauss không phân biệt)

#### 2.3.3 `role: "user"` — User message

**Dạng string** (hiếm gặp):
```json
{"role": "user", "content": "Xin chào"}
```

**Dạng array** (PHỔ BIẾN NHẤT):
```json
{
  "role": "user",
  "content": [
    {"type": "text", "text": "Máy CNC-01 bị lỗi gì?"}
  ]
}
```

**Dạng array với image** (Gauss không hỗ trợ, cần skip image):
```json
{
  "role": "user",
  "content": [
    {"type": "text", "text": "Hình này là gì?"},
    {"type": "image_url", "image_url": {"url": "data:image/png;base64,iVBOR..."}}
  ]
}
```

**Proxy xử lý**: normalize content → string (ghép text parts, bỏ image parts).

#### 2.3.4 `role: "assistant"` — Assistant response (từ conversation history)

```jsonc
{
  "role": "assistant",
  "content": [                                    // LUÔN là array (không bao giờ string)
    {"type": "text", "text": "Tôi sẽ tra cứu..."}
  ],
  // Xuất hiện khi assistant đã gọi tool:
  "tool_calls": [
    {
      "id": "call_abc123",
      "type": "function",
      "function": {
        "name": "read",
        "arguments": "{\"path\": \"/tmp/file.txt\"}"
      }
    }
  ]
}
```

**Proxy xử lý**:
- Normalize `content` array → string
- Nếu có `tool_calls` → chuyển thành text dạng `<tool_call>` (xem Section 5)

#### 2.3.5 `role: "tool"` — Tool result (kết quả thực thi tool)

```json
{
  "role": "tool",
  "tool_call_id": "call_abc123",
  "content": "File contents: hello world..."
}
```

**Proxy xử lý**: chuyển thành text dạng `[Tool Result: ...]` (xem Section 5)

### 2.4 Tools — Danh sách tool definitions

```json
{
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "read",
        "description": "Read file contents",
        "parameters": {
          "type": "object",
          "properties": {
            "file_path": {"type": "string", "description": "Path to the file"},
            "limit": {"type": "integer", "description": "Max lines to read"}
          },
          "required": ["file_path"]
        },
        "strict": false
      }
    },
    {
      "type": "function",
      "function": {
        "name": "exec",
        "description": "Run shell commands",
        "parameters": {
          "type": "object",
          "properties": {
            "command": {"type": "string", "description": "The command to execute"}
          },
          "required": ["command"]
        }
      }
    }
  ]
}
```

**Proxy xử lý**: chuyển thành text mô tả, inject vào system prompt (xem Section 5).

---

## 3. Response: Proxy trả về OpenClaw

### 3.1 Streaming Response — Text thuần (không có tool call)

**Headers:**
```
HTTP/1.1 200 OK
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive
```

**SSE chunks:**
```
data: {"id":"chatcmpl-<uuid>","object":"chat.completion.chunk","created":1700000000,"model":"gauss-2.3","choices":[{"index":0,"delta":{"role":"assistant","content":"Máy"},"finish_reason":null}]}

data: {"id":"chatcmpl-<uuid>","object":"chat.completion.chunk","created":1700000000,"model":"gauss-2.3","choices":[{"index":0,"delta":{"content":" CNC-01"},"finish_reason":null}]}

data: {"id":"chatcmpl-<uuid>","object":"chat.completion.chunk","created":1700000000,"model":"gauss-2.3","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}

data: [DONE]

```

**Quy tắc:**
- Chunk đầu: `delta` có `role` + `content`
- Chunk tiếp: `delta` chỉ có `content`
- Chunk cuối: `delta` rỗng `{}`, `finish_reason: "stop"`
- Kết thúc: `data: [DONE]`
- Mỗi chunk cách nhau bởi `\n\n`

### 3.2 Streaming Response — Có tool call (MỚI — do proxy giả lập)

Khi Gauss trả text chứa `<tool_call>`, proxy phải chuyển thành SSE `tool_calls` format.

**Ví dụ Gauss trả về:**
```
Tôi sẽ đọc file cho bạn.
<tool_call>{"name": "read", "arguments": {"file_path": "/tmp/file.txt"}}</tool_call>
```

**Proxy chuyển thành SSE:**
```
data: {"id":"chatcmpl-<uuid>","object":"chat.completion.chunk","created":1700000000,"model":"gauss-2.3","choices":[{"index":0,"delta":{"role":"assistant","content":"Tôi sẽ đọc file cho bạn.\n"},"finish_reason":null}]}

data: {"id":"chatcmpl-<uuid>","object":"chat.completion.chunk","created":1700000000,"model":"gauss-2.3","choices":[{"index":0,"delta":{"tool_calls":[{"index":0,"id":"call_proxy_<uuid>","type":"function","function":{"name":"read","arguments":"{\"file_path\": \"/tmp/file.txt\"}"}}]},"finish_reason":null}]}

data: {"id":"chatcmpl-<uuid>","object":"chat.completion.chunk","created":1700000000,"model":"gauss-2.3","choices":[{"index":0,"delta":{},"finish_reason":"tool_calls"}]}

data: [DONE]

```

**Quy tắc:**
- Text trước `<tool_call>` → gửi như content chunks bình thường
- Nội dung `<tool_call>` → chuyển thành `delta.tool_calls` chunk
- `finish_reason` = `"tool_calls"` (KHÔNG phải `"stop"`)
- `tool_calls[].id` = proxy tự generate: `"call_proxy_<uuid_8char>"`
- `tool_calls[].function.arguments` = **JSON string** (không phải object)

### 3.3 Non-Streaming Response (nếu `stream: false`)

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
  "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
}
```

**Non-streaming có tool call:**
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
        "content": "Tôi sẽ đọc file cho bạn.\n",
        "tool_calls": [
          {
            "id": "call_proxy_<uuid>",
            "type": "function",
            "function": {
              "name": "read",
              "arguments": "{\"file_path\": \"/tmp/file.txt\"}"
            }
          }
        ]
      },
      "finish_reason": "tool_calls"
    }
  ],
  "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
}
```

### 3.4 Error Response

```json
{
  "error": {
    "message": "Error description",
    "type": "invalid_request_error",
    "code": "model_not_found"
  }
}
```

---

## 4. Message Normalization (Bước 1 trong pipeline)

> Mục tiêu: chuyển tất cả messages từ format OpenClaw → format string đơn giản
> mà có thể ghép thành `input_value` + `system_message` cho Gauss.

### 4.1 Normalize `content` field

```
Input                                          Output
─────                                          ──────
"Hello" (string)                         →     "Hello"

[{"type": "text", "text": "Hello"}]      →     "Hello"

[{"type": "text", "text": "A"},          →     "A\nB"
 {"type": "text", "text": "B"}]

[{"type": "text", "text": "See img"},    →     "See img"
 {"type": "image_url", ...}]                   (bỏ image)

[] (empty array)                         →     ""

null / undefined                         →     ""
```

**Pseudocode:**
```python
def normalize_content(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = []
        for item in content:
            if isinstance(item, str):
                texts.append(item)
            elif isinstance(item, dict) and item.get("type") == "text":
                texts.append(item.get("text", ""))
            # Skip image_url, image, và các type khác
        return "\n".join(texts)
    if content is None:
        return ""
    return str(content)
```

### 4.2 Normalize `role` field

```
Input role        Output role       Ghi chú
──────────        ───────────       ───────
"system"     →    "system"          Giữ nguyên
"developer"  →    "system"          Reasoning models gửi developer thay system
"user"       →    "user"            Giữ nguyên
"assistant"  →    "assistant"       Giữ nguyên
"tool"       →    (xử lý đặc biệt) Xem Section 5.3
```

### 4.3 Tổng hợp messages → (system_message, input_value)

Sau khi normalize, ghép messages thành 2 string cho Gauss:

```python
def flatten_messages(normalized_messages) -> tuple[str, str]:
    system_message = ""
    non_system = []

    for msg in normalized_messages:
        if msg["role"] == "system":
            system_message = msg["content"]     # Lấy cuối cùng nếu nhiều
        elif msg["role"] == "user":
            non_system.append(msg)
        elif msg["role"] == "assistant":
            non_system.append(msg)
        elif msg["role"] == "tool":
            non_system.append(msg)              # Đã được convert ở bước tool translation

    if len(non_system) == 1 and non_system[0]["role"] == "user":
        return non_system[0]["content"], system_message

    # Multi-turn → formatted conversation
    parts = []
    role_map = {"user": "User", "assistant": "Assistant", "tool": "Tool Result"}
    for msg in non_system:
        prefix = role_map.get(msg["role"], msg["role"].capitalize())
        parts.append(f"{prefix}: {msg['content']}")
    return "\n".join(parts), system_message
```

---

## 5. Tool Translation (Bước 2 trong pipeline — PHẦN QUAN TRỌNG NHẤT)

> Giả lập OpenAI function calling cho LLM chỉ hỗ trợ text.
> Pattern đã được validate trong production: `machine-issue-solver/chatbot/app/graph.py`

### 5.1 Tools → Text Prompt (Request direction)

Khi request có `tools[]`, proxy chuyển thành text và **append vào cuối system prompt**.

**Input** (từ OpenClaw request):
```json
{
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "read",
        "description": "Read file contents",
        "parameters": {
          "type": "object",
          "properties": {
            "file_path": {"type": "string", "description": "Path to the file"},
            "limit": {"type": "integer", "description": "Max lines to read"}
          },
          "required": ["file_path"]
        }
      }
    },
    {
      "type": "function",
      "function": {
        "name": "exec",
        "description": "Run shell commands",
        "parameters": {
          "type": "object",
          "properties": {
            "command": {"type": "string", "description": "The command to execute"}
          },
          "required": ["command"]
        }
      }
    }
  ]
}
```

**Output** (append vào system prompt):
```

---
## Available Tools

You have access to the following tools. To use a tool, include EXACTLY this syntax in your response:
<tool_call>{"name": "<tool_name>", "arguments": {<args>}}</tool_call>

### Tools:

1. **read** — Read file contents
   Parameters:
   - file_path (string, required): Path to the file
   - limit (integer, optional): Max lines to read

2. **exec** — Run shell commands
   Parameters:
   - command (string, required): The command to execute

### Rules:
- Call only ONE tool per response
- If you don't need a tool, respond directly without <tool_call> tags
- After receiving tool results, use that data to answer the user
- Always include the tool name and all required arguments
```

**Pseudocode để generate tool prompt:**
```python
def tools_to_prompt(tools: list[dict]) -> str:
    if not tools:
        return ""

    lines = [
        "",
        "---",
        "## Available Tools",
        "",
        "You have access to the following tools. "
        "To use a tool, include EXACTLY this syntax in your response:",
        '<tool_call>{"name": "<tool_name>", "arguments": {<args>}}</tool_call>',
        "",
        "### Tools:",
        "",
    ]

    for i, tool in enumerate(tools, 1):
        func = tool.get("function", {})
        name = func.get("name", "unknown")
        desc = func.get("description", "No description")
        params = func.get("parameters", {})
        properties = params.get("properties", {})
        required = set(params.get("required", []))

        lines.append(f"{i}. **{name}** — {desc}")
        if properties:
            lines.append("   Parameters:")
            for prop_name, prop_schema in properties.items():
                prop_type = prop_schema.get("type", "any")
                prop_desc = prop_schema.get("description", "")
                req_str = "required" if prop_name in required else "optional"
                desc_str = f": {prop_desc}" if prop_desc else ""
                lines.append(f"   - {prop_name} ({prop_type}, {req_str}){desc_str}")
        lines.append("")

    lines.extend([
        "### Rules:",
        "- Call only ONE tool per response",
        "- If you don't need a tool, respond directly without <tool_call> tags",
        "- After receiving tool results, use that data to answer the user",
        "- Always include the tool name and all required arguments",
    ])

    return "\n".join(lines)
```

### 5.2 Assistant tool_calls → Text (Request direction)

Khi conversation history có assistant message với `tool_calls`, chuyển thành text.

**Input** (từ OpenClaw messages):
```json
{
  "role": "assistant",
  "content": [{"type": "text", "text": "I'll read the file."}],
  "tool_calls": [
    {
      "id": "call_abc123",
      "type": "function",
      "function": {
        "name": "read",
        "arguments": "{\"file_path\": \"/tmp/file.txt\"}"
      }
    }
  ]
}
```

**Output** (text cho conversation):
```
I'll read the file.
<tool_call>{"name": "read", "arguments": {"file_path": "/tmp/file.txt"}}</tool_call>
```

**Pseudocode:**
```python
def convert_assistant_message(msg: dict) -> str:
    """Convert assistant message with tool_calls to plain text."""
    text = normalize_content(msg.get("content"))

    tool_calls = msg.get("tool_calls", [])
    for tc in tool_calls:
        func = tc.get("function", {})
        name = func.get("name", "")
        # arguments là JSON string, parse thành object
        try:
            args = json.loads(func.get("arguments", "{}"))
        except json.JSONDecodeError:
            args = {}
        tool_call_text = json.dumps({"name": name, "arguments": args}, ensure_ascii=False)
        text += f"\n<tool_call>{tool_call_text}</tool_call>"

    return text.strip()
```

### 5.3 Tool Result Messages → Text (Request direction)

Khi conversation history có `role: "tool"` messages, chuyển thành text.

**Input** (từ OpenClaw messages):
```json
{
  "role": "tool",
  "tool_call_id": "call_abc123",
  "content": "File contents:\nhello world\nfoo bar"
}
```

**Output** (text message, role="user" trong flattened conversation):
```
[Tool Result]
hello world
foo bar
[/Tool Result]
```

**Pseudocode:**
```python
def convert_tool_result_message(msg: dict) -> dict:
    """Convert tool result message to a pseudo-user message."""
    content = normalize_content(msg.get("content", ""))
    return {
        "role": "tool",  # Sẽ được xử lý trong flatten_messages
        "content": f"[Tool Result]\n{content}\n[/Tool Result]"
    }
```

### 5.4 Parse Tool Call từ Gauss Response (Response direction)

Khi Gauss trả text chứa `<tool_call>`, proxy phải detect và chuyển thành OpenAI format.

**Detection patterns** (ưu tiên từ trên xuống):
```python
import re

# Pattern 1: XML-tagged (recommended, most reliable)
TOOL_CALL_PATTERN = re.compile(r'<tool_call>(.*?)</tool_call>', re.DOTALL)

# Pattern 2: Raw JSON fallback (khi model bỏ qua XML tags)
RAW_TOOL_CALL_PATTERN = re.compile(
    r'\{[^{}]*"name"\s*:\s*"[^"]+?"[^{}]*"arguments"\s*:\s*\{[^{}]*\}[^{}]*\}',
    re.DOTALL
)
```

**Pseudocode parse:**
```python
def parse_tool_call_from_text(text: str) -> tuple[str, dict | None]:
    """Parse tool call from Gauss response text.

    Returns:
        (text_before_tool_call, parsed_tool_call_or_None)

    parsed_tool_call format:
        {"name": "read", "arguments": {"file_path": "/tmp/file.txt"}}
    """
    # Try 1: XML-tagged
    match = TOOL_CALL_PATTERN.search(text)
    if match:
        try:
            tool_call = json.loads(match.group(1).strip())
            if "name" in tool_call and "arguments" in tool_call:
                text_before = text[:match.start()].strip()
                return text_before, tool_call
        except json.JSONDecodeError:
            pass

    # Try 2: Raw JSON
    match = RAW_TOOL_CALL_PATTERN.search(text)
    if match:
        try:
            tool_call = json.loads(match.group(0))
            if "name" in tool_call and "arguments" in tool_call:
                text_before = text[:match.start()].strip()
                return text_before, tool_call
        except json.JSONDecodeError:
            pass

    return text, None
```

### 5.5 Streaming Tool Call Detection (Response direction)

Vì Gauss stream text từng chunk, proxy cần **buffer** để detect `<tool_call>`:

```
Gauss stream chunks:           Proxy behavior:
──────────────────            ─────────────────
"Tôi sẽ "            →       Forward as content delta
"đọc file"            →       Forward as content delta
" cho bạn.\n"         →       Forward as content delta
"<tool"               →       START BUFFERING (detect opening tag)
"_call>{"             →       Continue buffering
"\"name\": \"read\""  →       Continue buffering
"}</tool_call>"       →       FLUSH: parse buffer → emit tool_calls delta
```

**Thuật toán streaming:**

```python
TOOL_CALL_OPEN = "<tool_call>"
TOOL_CALL_CLOSE = "</tool_call>"

class StreamingToolDetector:
    """Detect <tool_call> in streaming text chunks.

    States:
      PASSTHROUGH — forward text as-is
      BUFFERING   — accumulating potential tool call
    """

    def __init__(self):
        self.state = "PASSTHROUGH"
        self.buffer = ""
        self.pending_text = ""  # Text trước <tool_call> chưa gửi

    def feed(self, chunk: str) -> list[dict]:
        """Feed a text chunk, return list of events to emit.

        Event types:
          {"type": "text", "content": "..."}       — emit as content delta
          {"type": "tool_call", "tool_call": {...}} — emit as tool_calls delta
        """
        events = []
        self.buffer += chunk

        while self.buffer:
            if self.state == "PASSTHROUGH":
                # Tìm vị trí bắt đầu của <tool_call> hoặc prefix của nó
                tag_pos = self.buffer.find(TOOL_CALL_OPEN)

                if tag_pos == -1:
                    # Không thấy tag, nhưng buffer có thể chứa prefix
                    # Giữ lại phần cuối có thể là prefix: "<", "<t", "<to", ..., "<tool_cal"
                    safe_end = len(self.buffer)
                    for i in range(1, len(TOOL_CALL_OPEN)):
                        if self.buffer.endswith(TOOL_CALL_OPEN[:i]):
                            safe_end = len(self.buffer) - i
                            break
                    if safe_end > 0:
                        events.append({"type": "text", "content": self.buffer[:safe_end]})
                    self.buffer = self.buffer[safe_end:]
                    break  # Cần thêm data

                else:
                    # Thấy <tool_call> tag
                    if tag_pos > 0:
                        events.append({"type": "text", "content": self.buffer[:tag_pos]})
                    self.buffer = self.buffer[tag_pos + len(TOOL_CALL_OPEN):]
                    self.state = "BUFFERING"

            elif self.state == "BUFFERING":
                close_pos = self.buffer.find(TOOL_CALL_CLOSE)

                if close_pos == -1:
                    break  # Chờ thêm data cho closing tag

                # Thấy closing tag → parse tool call
                tool_json_str = self.buffer[:close_pos].strip()
                self.buffer = self.buffer[close_pos + len(TOOL_CALL_CLOSE):]
                self.state = "PASSTHROUGH"

                try:
                    tool_call = json.loads(tool_json_str)
                    if "name" in tool_call:
                        events.append({"type": "tool_call", "tool_call": tool_call})
                    else:
                        # Invalid format → emit as text
                        events.append({"type": "text",
                            "content": f"<tool_call>{tool_json_str}</tool_call>"})
                except json.JSONDecodeError:
                    events.append({"type": "text",
                        "content": f"<tool_call>{tool_json_str}</tool_call>"})

        return events

    def flush(self) -> list[dict]:
        """Flush remaining buffer when stream ends."""
        events = []
        if self.buffer:
            if self.state == "BUFFERING":
                # Incomplete tool call → emit as text
                events.append({"type": "text",
                    "content": f"<tool_call>{self.buffer}"})
            else:
                events.append({"type": "text", "content": self.buffer})
            self.buffer = ""
        self.state = "PASSTHROUGH"
        return events
```

### 5.6 Convert Parsed Tool Call → SSE Format

Sau khi detect tool call, chuyển thành SSE chunk:

```python
def tool_call_to_sse_delta(tool_call: dict, tool_call_index: int = 0) -> dict:
    """Convert parsed tool call to OpenAI SSE delta format.

    Input:  {"name": "read", "arguments": {"file_path": "/tmp/file.txt"}}
    Output: {"tool_calls": [{"index": 0, "id": "call_proxy_abc12345",
             "type": "function", "function": {"name": "read",
             "arguments": "{\"file_path\": \"/tmp/file.txt\"}"}}]}
    """
    call_id = f"call_proxy_{uuid.uuid4().hex[:8]}"
    arguments = tool_call.get("arguments", {})
    if isinstance(arguments, dict):
        arguments = json.dumps(arguments, ensure_ascii=False)

    return {
        "tool_calls": [
            {
                "index": tool_call_index,
                "id": call_id,
                "type": "function",
                "function": {
                    "name": tool_call["name"],
                    "arguments": arguments,
                },
            }
        ]
    }
```

---

## 6. Tổng hợp: Request Processing Pipeline

```
OpenClaw Request
      │
      ▼
┌─────────────────────────────────────────────┐
│ Step 1: Validate & Extract                  │
│   - Pydantic parse body (extra="ignore")    │
│   - Extract: model, messages, tools,        │
│     temperature, stream, max_*_tokens       │
├─────────────────────────────────────────────┤
│ Step 2: Normalize Messages                  │
│   - content array → string                  │
│   - role "developer" → "system"             │
│   - Skip image content parts                │
├─────────────────────────────────────────────┤
│ Step 3: Tool Translation (Request)          │
│   - tools[] → text prompt (append system)   │
│   - assistant tool_calls → <tool_call> text │
│   - role:"tool" → [Tool Result] text        │
├─────────────────────────────────────────────┤
│ Step 4: Flatten Messages                    │
│   - Extract system_message                  │
│   - Build input_value (multi-turn concat)   │
├─────────────────────────────────────────────┤
│ Step 5: Call Gauss                          │
│   - build_request_body()                    │
│   - POST {model-url}?stream=true/false      │
├─────────────────────────────────────────────┤
│ Step 6: Tool Translation (Response)         │
│   - Detect <tool_call> in text              │
│   - Text before → content chunks            │
│   - Tool call → tool_calls chunks           │
│   - Set finish_reason accordingly           │
├─────────────────────────────────────────────┤
│ Step 7: Return SSE/JSON Response            │
│   - Format as OpenAI response               │
└─────────────────────────────────────────────┘
      │
      ▼
OpenClaw receives response
```

---

## 7. Company LLM API (Phía Proxy gọi đi)

> Không thay đổi so với bản hiện tại. Giữ nguyên `gauss_client.py`.

### 7.1 Non-Streaming

```
POST {model-url}?stream=false
Headers: Content-Type: application/json, x-api-key: <key>
```
```json
{
  "component_inputs": {
    "<model-id>": {
      "input_value": "<flattened_prompt>",
      "max_retries": 3,
      "parameters": "{\"temperature\": 0, \"top_p\": 0.95}",
      "stream": false,
      "system_message": "<system_prompt + tool_descriptions>"
    }
  }
}
```

### 7.2 Streaming

```
POST {model-url}?stream=true
```
```json
{
  "component_inputs": {
    "<model-id>": {
      "input_value": "<flattened_prompt>",
      "max_retries": 0,
      "parameters": "{\"temperature\": 0, \"top_p\": 0.95, \"extra_body\": {\"repetition_penalty\": 1.05}}",
      "stream": true,
      "system_message": "<system_prompt + tool_descriptions>"
    }
  }
}
```

### 7.3 Response format

**Non-streaming**: xem `gauss_client.py` `parse_response()` — 2 format (dict/string).

**Streaming**: JSON-lines, mỗi dòng `{"event": "token", "data": {"chunk": "<text>"}}`.

---

## 8. Ví dụ End-to-End

### 8.1 Chat đơn giản (không có tools)

**OpenClaw gửi:**
```json
{
  "model": "gauss-2.3",
  "messages": [
    {"role": "system", "content": "You are helpful."},
    {"role": "user", "content": [{"type": "text", "text": "Xin chào"}]}
  ],
  "stream": true,
  "stream_options": {"include_usage": true},
  "store": false,
  "max_completion_tokens": 8192
}
```

**Proxy normalize:**
- system_message = `"You are helpful."`
- input_value = `"Xin chào"`
- Không có tools → không inject tool prompt

**Proxy → Gauss:**
```json
{"component_inputs": {"model-id": {"input_value": "Xin chào", "system_message": "You are helpful.", ...}}}
```

**Gauss → Proxy (stream):** `"Chào"`, `" bạn"`, `"!"`, `" Tôi"`, ...

**Proxy → OpenClaw (SSE):**
```
data: {"id":"chatcmpl-abc","object":"chat.completion.chunk","created":1700000000,"model":"gauss-2.3","choices":[{"index":0,"delta":{"role":"assistant","content":"Chào"},"finish_reason":null}]}

data: {"id":"chatcmpl-abc","object":"chat.completion.chunk","created":1700000000,"model":"gauss-2.3","choices":[{"index":0,"delta":{"content":" bạn"},"finish_reason":null}]}

...

data: {"id":"chatcmpl-abc","object":"chat.completion.chunk","created":1700000000,"model":"gauss-2.3","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}

data: [DONE]

```

### 8.2 Lần đầu gọi tool (OpenClaw gửi tools[], Gauss quyết định dùng tool)

**OpenClaw gửi:**
```json
{
  "model": "gauss-2.3",
  "messages": [
    {"role": "system", "content": "You are a coding assistant."},
    {"role": "user", "content": [{"type": "text", "text": "Read the file /tmp/hello.txt"}]}
  ],
  "tools": [
    {"type": "function", "function": {"name": "read", "description": "Read file contents", "parameters": {"type": "object", "properties": {"file_path": {"type": "string"}}, "required": ["file_path"]}}}
  ],
  "stream": true
}
```

**Proxy xử lý request:**
- system_message = `"You are a coding assistant.\n\n---\n## Available Tools\n..."` (inject tool prompt)
- input_value = `"Read the file /tmp/hello.txt"`

**Gauss trả về (stream):**
```
"I'll read that file for you.\n<tool_call>{\"name\": \"read\", \"arguments\": {\"file_path\": \"/tmp/hello.txt\"}}</tool_call>"
```

**Proxy detect `<tool_call>` và trả SSE:**
```
data: {"id":"chatcmpl-abc","object":"chat.completion.chunk","created":1700000000,"model":"gauss-2.3","choices":[{"index":0,"delta":{"role":"assistant","content":"I'll read that file for you.\n"},"finish_reason":null}]}

data: {"id":"chatcmpl-abc","object":"chat.completion.chunk","created":1700000000,"model":"gauss-2.3","choices":[{"index":0,"delta":{"tool_calls":[{"index":0,"id":"call_proxy_a1b2c3d4","type":"function","function":{"name":"read","arguments":"{\"file_path\": \"/tmp/hello.txt\"}"}}]},"finish_reason":null}]}

data: {"id":"chatcmpl-abc","object":"chat.completion.chunk","created":1700000000,"model":"gauss-2.3","choices":[{"index":0,"delta":{},"finish_reason":"tool_calls"}]}

data: [DONE]

```

### 8.3 Lần tiếp theo (OpenClaw gửi tool result, Gauss trả lời cuối)

**OpenClaw gửi (sau khi thực thi tool):**
```json
{
  "model": "gauss-2.3",
  "messages": [
    {"role": "system", "content": "You are a coding assistant."},
    {"role": "user", "content": [{"type": "text", "text": "Read the file /tmp/hello.txt"}]},
    {
      "role": "assistant",
      "content": [{"type": "text", "text": "I'll read that file for you.\n"}],
      "tool_calls": [{"id": "call_proxy_a1b2c3d4", "type": "function", "function": {"name": "read", "arguments": "{\"file_path\": \"/tmp/hello.txt\"}"}}]
    },
    {
      "role": "tool",
      "tool_call_id": "call_proxy_a1b2c3d4",
      "content": "Hello World!\nThis is a test file."
    }
  ],
  "tools": [
    {"type": "function", "function": {"name": "read", "description": "Read file contents", "parameters": {"type": "object", "properties": {"file_path": {"type": "string"}}, "required": ["file_path"]}}}
  ],
  "stream": true
}
```

**Proxy xử lý request:**
- system_message = `"You are a coding assistant.\n\n---\n## Available Tools\n..."` (inject tool prompt)
- Messages normalize:
  ```
  User: Read the file /tmp/hello.txt
  Assistant: I'll read that file for you.
  <tool_call>{"name": "read", "arguments": {"file_path": "/tmp/hello.txt"}}</tool_call>
  Tool Result: [Tool Result]
  Hello World!
  This is a test file.
  [/Tool Result]
  ```
- input_value = toàn bộ formatted conversation ở trên

**Gauss trả về (stream):**
```
"The file /tmp/hello.txt contains:\n\n```\nHello World!\nThis is a test file.\n```"
```

**Proxy detect KHÔNG có `<tool_call>` → trả text bình thường, `finish_reason: "stop"`.**

---

## 9. Model Registry

| Model ID (OpenClaw gửi) | Reasoning? | System role | Ghi chú |
|--------------------------|------------|-------------|---------|
| `gauss-2.3` | No | `system` | Model mặc định |
| `gauss-2.3-think` | Yes* | `developer` | *Gauss không có reasoning, proxy coi developer=system |
| `gausso-flash` | No | `system` | Nhanh |
| `gausso-flash-s` | No | `system` | Nhỏ hơn |
| `gausso4` | Yes* | `developer` | *Tương tự |
| `gausso4-thinking` | Yes* | `developer` | *Tương tự |

---

## 10. Error Handling

| HTTP Status | Khi nào | Body |
|-------------|---------|------|
| 400 | Messages rỗng, không có non-system message | `{"error": {"message": "...", "type": "invalid_request_error"}}` |
| 401 | Thiếu API key | `{"error": {"message": "...", "type": "authentication_error"}}` |
| 404 | Model không tồn tại | `{"error": {"message": "...", "type": "invalid_request_error", "code": "model_not_found"}}` |
| 422 | Request body không hợp lệ (Pydantic) | `{"detail": [{"loc": [...], "msg": "...", "type": "..."}]}` |
| 500 | Gauss trả lỗi / parse fail | `{"error": {"message": "...", "type": "server_error"}}` |
| 502 | Không kết nối được Gauss | `{"error": {"message": "...", "type": "server_error"}}` |
| 504 | Gauss timeout | `{"error": {"message": "...", "type": "server_error"}}` |

Streaming error (giữa stream):
```
data: {"id":"chatcmpl-...","choices":[{"index":0,"delta":{},"finish_reason":"error"}]}

data: [DONE]

```

---

## 11. Configuration

| Variable | Mặc định | Mô tả |
|----------|----------|-------|
| `PROXY_HOST` | `0.0.0.0` | Host bind |
| `PROXY_PORT` | `9000` | Port |
| `COMPANY_LLM_API_KEY` | (bắt buộc) | API key cho Company LLM |
| `COMPANY_LLM_MODEL_ID` | `null` | Override model-id |
| `COMPANY_LLM_MODEL_URL` | `null` | Override model-url |
| `DEFAULT_TEMPERATURE` | `0` | Temperature mặc định |
| `DEFAULT_TOP_P` | `0.95` | Top-p mặc định |
| `REQUEST_TIMEOUT` | `60` | Timeout (giây) |
| `SSL_VERIFY` | `false` | SSL verification |
| `LOG_LEVEL` | `INFO` | Log level |
| `TOOL_CALL_ENABLED` | `true` | Bật/tắt tool translation |
| `TOOL_MAX_PER_RESPONSE` | `1` | Số tool call tối đa mỗi response |

---

## 12. File Structure

```
gauss-openai-proxy/app/
├── main.py              — FastAPI server, endpoints, request/response orchestration
├── schemas.py           — Pydantic models (request + response)
├── config.py            — Environment config + model registry
├── gauss_client.py      — HTTP client cho Company LLM (không thay đổi)
├── tool_translation.py  — NEW: tools↔text conversion, streaming tool detection
└── message_normalize.py — NEW: content/role normalization, message flattening
```
