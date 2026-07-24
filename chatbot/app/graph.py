"""
Machine Issue Solver — ReAct Agent (LangGraph prebuilt).

Uses ``langgraph.prebuilt.create_react_agent`` with an OpenAI-compatible
``ChatOpenAI`` model and native tool calling — the standard ReAct loop is
handled by LangGraph instead of a hand-rolled generator.

A contextvar recorder carries the tool's structured results (issues found) out
of the graph so the UI can show the "related issues" panel and feedback, the
same role the old side-channel played. The streaming event interface
(``status`` / ``chunk`` dicts + ``StreamResult``) is unchanged, so the Streamlit
chat page needs no edits.

Langfuse: the ReAct run is traced via the LangChain CallbackHandler (adopted
from the chat-with-documents project); an outer @observe span owns the trace_id
that the (unchanged) feedback mechanism scores against.
"""

import contextvars
from typing import Optional, List, Dict

from langchain_core.messages import AIMessageChunk
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from langfuse import observe, get_client

from llm import get_chat_model
from langfuse_setup import langchain_handler, trace_attributes, flush_langfuse
from api_client import search_issues_sync
from logger import logger, Timer


# Max tool-using steps before LangGraph stops (recursion_limit = 2*N + 1).
MAX_ITERATIONS = 3

SYSTEM_PROMPT = """Bạn là "Machine Issue Solver" — trợ lý kỹ thuật chuyên về các vấn đề máy móc trong nhà máy.

Nhiệm vụ của bạn:
- Trả lời câu hỏi về vấn đề máy móc dựa trên dữ liệu trong cơ sở dữ liệu.
- Trả lời câu hỏi chung về bản thân và khả năng của bạn.
- Dùng lịch sử hội thoại để hiểu ngữ cảnh (ví dụ nếu người dùng đã nói về Line 2 trước đó thì không cần hỏi lại).

Khi cần dữ liệu thực tế về sự cố của một máy, hãy dùng công cụ `search_issues`.
Sau khi có kết quả công cụ, hãy trả lời người dùng tự nhiên dựa trên kết quả, KHÔNG bịa thông tin.

Quy tắc trả lời:
- Trả lời bằng tiếng Việt nếu người dùng dùng tiếng Việt.
- Ngắn gọn, rõ ràng, tập trung vào vấn đề.
"""

# Side-channel: the tool pushes the issues it found into this list so the UI
# (related-issues panel) and feedback can read them after the run.
_issues_recorder: contextvars.ContextVar[Optional[List[Dict]]] = contextvars.ContextVar(
    "issues_recorder", default=None
)


def format_issues_for_scratchpad(issues: List[Dict]) -> str:
    """Format issue list as readable text returned to the agent as the tool result."""
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


@tool
def search_issues(machine_name: str, line_name: str,
                  location: Optional[str] = None, serial: Optional[str] = None) -> str:
    """Tra cứu các vấn đề (issue) đã ghi nhận của một máy cụ thể trên một line cụ thể.

    Gọi công cụ này mỗi khi cần thông tin sự cố / nguyên nhân / cách khắc phục từ
    cơ sở dữ liệu. KHÔNG gọi cho câu chào hỏi hay câu hỏi chung không liên quan máy móc.

    Args:
        machine_name: Tên máy, ví dụ 'CNC-01' (bắt buộc).
        line_name: Tên hoặc số line, ví dụ 'Line 2' (bắt buộc).
        location: Vị trí của máy (chỉ thêm khi người dùng cung cấp).
        serial: Số serial của máy (chỉ thêm khi người dùng cung cấp).
    """
    try:
        with Timer(f"Tool: search_issues({machine_name}, {line_name}, location={location}, serial={serial})"):
            issues = search_issues_sync(machine_name, line_name, location=location, serial=serial)
    except Exception as e:
        logger.error(f"Tool execution error: {e}")
        return f"Lỗi khi gọi tool 'search_issues': {e}"

    rec = _issues_recorder.get()
    if rec is not None:
        rec.clear()
        if issues:
            rec.extend(issues)

    if not issues:
        desc = f"máy '{machine_name}' trên line '{line_name}'"
        if location:
            desc += f" tại Location '{location}'"
        if serial:
            desc += f" với Serial '{serial}'"
        return f"Không tìm thấy vấn đề nào cho {desc}."
    return format_issues_for_scratchpad(issues)


TOOLS = [search_issues]


def _tool_status_message(tool_name: str) -> str:
    """User-facing status shown while a tool runs."""
    if tool_name == "search_issues":
        return "Đang tra cứu cơ sở dữ liệu sự cố..."
    return f"Đang thực hiện: {tool_name}..."


def _build_messages(query: str, history: List[Dict[str, str]]) -> List[tuple]:
    """Prior turns (memory) + current question, as (role, text) tuples.

    The system prompt is supplied separately via create_react_agent(prompt=...).
    """
    msgs: List[tuple] = []
    for h in history or []:
        role = "user" if h.get("role") == "user" else "assistant"
        content = (h.get("content") or "").strip()
        if content:
            msgs.append((role, content))
    msgs.append(("user", query))
    return msgs


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

    Drives a LangGraph ReAct agent (create_react_agent) and streams only the
    assistant's answer tokens; tool-call chunks and tool observations are not
    shown. Issues found by the tool are collected via a contextvar recorder.
    """
    logger.info(f"Processing query (streaming): {query}")
    history = history or []

    issues_box: List[Dict] = []
    token = _issues_recorder.set(issues_box)

    try:
        llm = get_chat_model(api_key=api_key)
        agent = create_react_agent(llm, TOOLS, prompt=SYSTEM_PROMPT)
        messages = _build_messages(query, history)

        config = {"recursion_limit": 2 * MAX_ITERATIONS + 1}
        handler = langchain_handler()  # None when Langfuse is not configured
        if handler:
            config["callbacks"] = [handler]

        with trace_attributes(session_id=session_id or "", user_id=user_id or "",
                              trace_name="chat_query"):
            if result is not None:
                try:
                    result.trace_id = get_client().get_current_trace_id()
                except Exception:
                    pass

            yield {"type": "status", "message": "Đang phân tích câu hỏi..."}

            announced_tools = set()
            with Timer("ReAct agent stream"):
                for chunk, _meta in agent.stream(
                    {"messages": messages}, config=config, stream_mode="messages"
                ):
                    if not isinstance(chunk, AIMessageChunk):
                        continue  # skip ToolMessage observations etc.

                    for tcc in (getattr(chunk, "tool_call_chunks", None) or []):
                        name = tcc.get("name")
                        if name and name not in announced_tools:
                            announced_tools.add(name)
                            yield {"type": "status", "message": _tool_status_message(name)}

                    if chunk.content:
                        yield {"type": "chunk", "text": chunk.content}

            if result is not None:
                result.issues = list(issues_box)

    except Exception as e:
        logger.error(f"Streaming error: {e}", exc_info=True)
        if result is not None:
            result.error = str(e)
    finally:
        try:
            flush_langfuse()
        except Exception:
            pass
        _issues_recorder.reset(token)
    return
