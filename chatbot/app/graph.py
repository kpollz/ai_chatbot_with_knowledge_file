"""
Machine Issue Solver — Streaming ReAct Agent (native tool calling)

Uses an OpenAI-compatible chat model with native function/tool calling
(via LangChain ``bind_tools``). The model decides when to call a tool; tool
calls arrive as structured data on the streamed ``AIMessageChunk`` — no more
text/regex ``<tool_call>`` parsing.

Flow:
  LLM stream → tool_calls? → YES: execute tool(s), append ToolMessage → LLM stream (final)
                    ↓ NO
             stream answer directly to user
"""

from typing import Optional, List, Dict
from contextlib import nullcontext
import json

from langchain_core.messages import (
    SystemMessage, HumanMessage, AIMessage, ToolMessage, BaseMessage,
)
from langfuse import observe, propagate_attributes, get_client

from llm import get_chat_model
from api_client import search_issues_sync
from logger import logger, Timer


MAX_ITERATIONS = 3

SYSTEM_PROMPT = """Bạn là "Machine Issue Solver" — trợ lý kỹ thuật chuyên về các vấn đề máy móc trong nhà máy.

Nhiệm vụ của bạn:
- Trả lời câu hỏi về vấn đề máy móc dựa trên dữ liệu trong cơ sở dữ liệu.
- Trả lời câu hỏi chung về bản thân và khả năng của bạn.
- Dùng lịch sử hội thoại để hiểu ngữ cảnh (ví dụ nếu người dùng đã nói về Line 2 trước đó thì không cần hỏi lại).

Bạn có công cụ `search_issues` để tra cứu các vấn đề đã ghi nhận của một máy trên một line.
- Chỉ gọi công cụ khi cần dữ liệu thực tế từ cơ sở dữ liệu.
- `machine_name` và `line_name` là bắt buộc; `location` và `serial` chỉ thêm khi người dùng cung cấp.
- Sau khi có kết quả công cụ, hãy trả lời người dùng tự nhiên dựa trên kết quả, KHÔNG bịa thông tin.

Quy tắc trả lời:
- Trả lời bằng tiếng Việt nếu người dùng dùng tiếng Việt.
- Ngắn gọn, rõ ràng, tập trung vào vấn đề.
"""

# Native tool schema (OpenAI function format) passed to ``llm.bind_tools``.
SEARCH_ISSUES_TOOL = {
    "type": "function",
    "function": {
        "name": "search_issues",
        "description": "Tra cứu các vấn đề (issue) đã ghi nhận của một máy cụ thể trên một line cụ thể.",
        "parameters": {
            "type": "object",
            "properties": {
                "machine_name": {"type": "string", "description": "Tên máy, ví dụ 'CNC-01'."},
                "line_name": {"type": "string", "description": "Tên hoặc số line, ví dụ 'Line 2'."},
                "location": {"type": "string", "description": "Vị trí của máy (tùy chọn)."},
                "serial": {"type": "string", "description": "Số serial của máy (tùy chọn)."},
            },
            "required": ["machine_name", "line_name"],
        },
    },
}

TOOLS = [SEARCH_ISSUES_TOOL]
VALID_TOOLS = {"search_issues"}


def format_issues_for_scratchpad(issues: List[Dict]) -> str:
    """Format issue list as readable text for the tool result message."""
    if not issues:
        return "Không tìm thấy vấn đề nào."

    lines = [f"Tìm thấy {len(issues)} vấn đề:\n"]
    for i, issue in enumerate(issues, 1):
        lines.append(f"Vấn đề {i}:")
        lines.append(f"  ID: {issue.get('IssueID', 'N/A')}")
        lines.append(f"  Hiện tượng (Symptom): {issue.get('symptom', 'N/A')}")
        lines.append(f"  Nguyên Nhân (Cause): {issue.get('cause', 'N/A')}")
        lines.append(f"  Khắc phục (Solution): {issue.get('solution', 'N/A')}")
        lines.append(f"  PIC: {issue.get('PIC', 'N/A')}")
        lines.append("")
    return "\n".join(lines)


def _build_messages(query: str, history: List[Dict[str, str]]) -> List[BaseMessage]:
    """Build a proper multi-turn message array: system + history + current query."""
    messages: List[BaseMessage] = [SystemMessage(content=SYSTEM_PROMPT)]
    for msg in history or []:
        role = msg.get("role", "")
        content = msg.get("content", "") or ""
        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role == "assistant":
            messages.append(AIMessage(content=content))
    messages.append(HumanMessage(content=query))
    return messages


@observe(name="tool_execution")
def _execute_tool(name: str, args: Dict) -> tuple:
    """Execute a tool call. Returns (result_text, issues_found)."""
    if name == "search_issues":
        machine_name = args.get("machine_name", "") or ""
        line_name = args.get("line_name", "") or ""
        location = args.get("location") or None
        serial = args.get("serial") or None
        try:
            with Timer(f"Tool: search_issues({machine_name}, {line_name}, location={location}, serial={serial})"):
                issues = search_issues_sync(machine_name, line_name, location=location, serial=serial)
        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            return f"Lỗi khi gọi tool 'search_issues': {e}", []

        if not issues:
            desc = f"máy '{machine_name}' trên line '{line_name}'"
            if location:
                desc += f" tại Location '{location}'"
            if serial:
                desc += f" với Serial '{serial}'"
            return f"Không tìm thấy vấn đề nào cho {desc}.", []
        return format_issues_for_scratchpad(issues), issues

    return f"Tool '{name}' không được hỗ trợ.", []


def _tool_status_message(tool_name: str, tool_args: Dict) -> str:
    """User-friendly status message shown while a tool runs."""
    if tool_name == "search_issues":
        machine = tool_args.get("machine_name", "")
        line = tool_args.get("line_name", "")
        location = tool_args.get("location")
        serial = tool_args.get("serial")
        msg = f"Đang tìm kiếm vấn đề: {machine} trên {line}"
        if location:
            msg += f", Location {location}"
        if serial:
            msg += f", Serial {serial}"
        return msg + "..."
    return f"Đang thực hiện: {tool_name}..."


class StreamResult:
    """Side-channel to pass metadata (issues, errors, trace_id) out of the stream generator."""
    def __init__(self):
        self.issues: List[Dict] = []
        self.error: Optional[str] = None
        self.trace_id: Optional[str] = None


@observe(
    name="agent_solve_issue",
    transform_to_string=lambda events: "".join(
        e.get("text", "") for e in events if isinstance(e, dict) and e.get("type") == "chunk"
    ),
)
def solve_issue_stream(query: str, history: List[Dict[str, str]] = None,
                       api_key: str = "", result: Optional[StreamResult] = None,
                       session_id: str = None, user_id: str = None):
    """
    Streaming generator yielding event dicts for Streamlit rendering.

    Event types:
      {"type": "status", "message": "..."}  — progress indicator for UI
      {"type": "chunk",  "text": "..."}     — text chunk to append to response

    transform_to_string merges all chunk events into a single string for the
    Langfuse output. Nested @observe calls (tool_execution) attach to the
    active trace via propagate_attributes().
    """
    logger.info(f"Processing query (streaming): {query}")
    history = history or []

    # Langfuse v4: propagate session_id / user_id to all nested observations.
    propagate_kwargs = {}
    if session_id:
        propagate_kwargs["session_id"] = session_id
    if user_id:
        propagate_kwargs["user_id"] = user_id

    all_issues: List[Dict] = []

    llm = get_chat_model(api_key=api_key).bind_tools(TOOLS)
    messages = _build_messages(query, history)

    try:
        _attr_ctx = propagate_attributes(**propagate_kwargs) if propagate_kwargs else nullcontext()
    except Exception as lf_err:
        logger.debug(f"Langfuse propagate_attributes skipped: {lf_err}")
        _attr_ctx = nullcontext()

    with _attr_ctx:
        try:
            # Capture trace_id for feedback scoring.
            if result is not None:
                try:
                    result.trace_id = get_client().get_current_trace_id()
                except Exception:
                    pass

            first_turn = True
            for iteration in range(MAX_ITERATIONS + 1):
                yield {"type": "status",
                       "message": "Đang phân tích câu hỏi..." if first_turn else "Đang viết câu trả lời..."}

                gathered = None
                with Timer(f"LLM streaming call (iteration {iteration})"):
                    for chunk in llm.stream(messages):
                        gathered = chunk if gathered is None else gathered + chunk
                        if chunk.content:
                            yield {"type": "chunk", "text": chunk.content}

                tool_calls = list(getattr(gathered, "tool_calls", None) or []) if gathered is not None else []

                if not tool_calls:
                    # Direct answer — already streamed to the user.
                    break

                # Model requested tool(s): record the assistant turn, run them, feed results back.
                messages.append(AIMessage(content=gathered.content or "", tool_calls=tool_calls))
                for tc in tool_calls:
                    name = tc.get("name", "")
                    args = tc.get("args", {}) or {}
                    tc_id = tc.get("id")
                    logger.info(f"Agent wants tool: {name}({json.dumps(args, ensure_ascii=False)})")

                    yield {"type": "status", "message": _tool_status_message(name, args)}
                    result_text, issues_found = _execute_tool(name, args)
                    if issues_found:
                        all_issues = issues_found
                    messages.append(ToolMessage(content=result_text, tool_call_id=tc_id))

                first_turn = False

            if result is not None:
                result.issues = all_issues
            return

        except Exception as e:
            logger.error(f"Streaming error: {e}", exc_info=True)
            if result is not None:
                result.error = str(e)
            return
