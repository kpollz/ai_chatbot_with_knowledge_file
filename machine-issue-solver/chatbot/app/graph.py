"""
Machine Issue Solver — Streaming ReAct Agent (Custom Implementation)

Architecture: Text-based tool calling for LLMs without native function support.
Custom streaming implementation that buffers tokens to detect <tool_call> patterns.

Flow:
  LLM Stream (1st call) → Detect tool call? → YES: Execute tool → LLM Stream (final)
                                   ↓ NO
                          Stream directly to user
"""

from typing import Optional, List, Dict
from contextlib import nullcontext
import json
import re

from langchain_core.messages import SystemMessage, HumanMessage
from langfuse import observe, propagate_attributes
from config import LLM_MODEL, LLM_TEMPERATURE
from company_chat_model import get_company_llm
from api_client import search_issues_sync
from history import format_history_for_prompt
from logger import logger, Timer


MAX_ITERATIONS = 3
TOOL_CALL_PATTERN = re.compile(r'<tool_call>(.*?)</tool_call>', re.DOTALL)
RAW_TOOL_CALL_PATTERN = re.compile(r'\{[^{}]*"tool"\s*:\s*"[^"]+?"[^{}]*"args"\s*:\s*\{[^{}]*\}[^{}]*\}', re.DOTALL)

SYSTEM_PROMPT = """Ban la "Machine Issue Solver" — tro ly ky thuat chuyen ve cac van de may moc trong nha may.

Nhiem vu cua ban:
- Tra loi cac cau hoi ve van de may moc dua tren du lieu trong co so du lieu
- Tra loi cac cau hoi chung ve ban than va kha nang cua ban
- Su dung lich su hoi thoai de hieu ngu canh (vi du: neu nguoi dung da noi ve Line 2 truoc do, khong can hoi lai)

Ban co the su dung tool sau:

search_issues(machine_name: str, line_name: str, location: str = null, serial: str = null)
   Tim kiem cac van de lien quan den mot may cu the tren mot line cu the.
   - machine_name va line_name la bat buoc.
   - location va serial la tuy chon (optional). Chi them vao khi nguoi dung cung cap thong tin nay.
   - Vi du: neu nguoi dung noi "may CNC-01 tai vi tri A2" thi them location="A2".

Quy tac su dung tool:
- Chi goi MOT tool moi lan phan hoi.
- Khi can goi tool, hay tra loi CHI voi tool call (khong them giai thich).
- Tool call phai dung dinh dang:
  <tool_call>{"tool": "ten_tool", "args": {"arg1": "gia_tri"}}</tool_call>
- Sau khi tool tra ket qua, hay tra loi nguoi dung tu nhien (KHONG goi tool nua).

Quy tac tra loi:
- Tra loi bang tieng Viet neu nguoi dung dung tieng Viet.
- Tra loi ngan gon, ro rang, tap trung vao van de.
- Dua tren ket qua tool de tra loi, khong tuong tuong ra thong tin.
"""

VALID_TOOLS = {"search_issues"}


def parse_tool_call(text: str) -> Optional[Dict]:
    """Extract tool call from LLM response text.

    Supports two formats:
      1. <tool_call>{"tool": "...", "args": {...}}</tool_call>  (heavy model)
      2. {"tool": "...", "args": {...}}                         (fast model)
    """
    # Try 1: XML-tagged format
    match = TOOL_CALL_PATTERN.search(text)
    if match:
        try:
            tool_call = json.loads(match.group(1).strip())
            if tool_call.get("tool") in VALID_TOOLS:
                return tool_call
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse tool call JSON: {match.group(1)}")

    # Try 2: Raw JSON format (fast model)
    match = RAW_TOOL_CALL_PATTERN.search(text)
    if match:
        try:
            tool_call = json.loads(match.group(0))
            if tool_call.get("tool") in VALID_TOOLS:
                logger.info(f"Detected raw JSON tool call (no XML tags)")
                return tool_call
        except json.JSONDecodeError:
            pass

    return None


def clean_response(text: str) -> str:
    """Remove tool call patterns and clean up the response text."""
    cleaned = TOOL_CALL_PATTERN.sub("", text)
    cleaned = RAW_TOOL_CALL_PATTERN.sub("", cleaned)
    return cleaned.strip()


def format_issues_for_scratchpad(issues: List[Dict]) -> str:
    """Format issue list as readable text for the agent scratchpad."""
    if not issues:
        return "Không tìm thấy vấn đề nào."

    lines = [f"Tìm thấy {len(issues)} vấn đề:\n"]
    for i, issue in enumerate(issues, 1):
        lines.append(f"Vấn đề {i}:")
        lines.append(f"  ID: {issue.get('IssueID', 'N/A')}")
        lines.append(f"  Hiện tượng (Symptom): {issue.get('hien_tuong', 'N/A')}")
        lines.append(f"  Nguyên Nhân (Cause): {issue.get('nguyen_nhan', 'N/A')}")
        lines.append(f"  Khắc phục (Solution): {issue.get('khac_phuc', 'N/A')}")
        lines.append(f"  PIC: {issue.get('PIC', 'N/A')}")
        lines.append("")
    return "\n".join(lines)


def _build_agent_messages(query: str, history: List[Dict[str, str]],
                          scratchpad: str) -> list:
    """Build LLM messages for agent call."""
    parts = []
    history_text = format_history_for_prompt(history)
    if history_text:
        parts.append(history_text)
    parts.append(f"Câu hỏi hiện tại của người dùng: {query}")
    if scratchpad:
        parts.append(
            f"\n{scratchpad}\n"
            "Dựa trên kết quả tool ở trên, hãy trả lời người dùng chi tiết và hữu ích. "
            "KHÔNG gọi thêm tool nếu không cần thiết."
        )
    user_prompt = "\n\n".join(parts)
    return [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=user_prompt)]


@observe(name="tool_execution")
def _execute_tool_sync(tool_call: Dict) -> tuple:
    """Execute a tool call synchronously. Returns (result_text, issues_found)."""
    tool_name = tool_call.get("tool", "")
    tool_args = tool_call.get("args", {})
    result_text = ""
    issues_found = []

    try:
        if tool_name == "search_issues":
            machine_name = tool_args.get("machine_name", "")
            line_name = tool_args.get("line_name", "")
            location = tool_args.get("location")
            serial = tool_args.get("serial")
            with Timer(f"Tool: search_issues({machine_name}, {line_name}, location={location}, serial={serial})"):
                issues = search_issues_sync(machine_name, line_name, location=location, serial=serial)
            issues_found = issues
            if not issues:
                desc = f"Máy '{machine_name}' trên line '{line_name}'"
                if location:
                    desc += f" tại Location '{location}'"
                if serial:
                    desc += f" với Serial '{serial}'"
                result_text = f"Không tìm thấy vấn đề nào cho {desc}."
            else:
                result_text = format_issues_for_scratchpad(issues)
        else:
            result_text = f"Tool '{tool_name}' không được hỗ trợ."

    except Exception as e:
        logger.error(f"Tool execution error: {e}")
        result_text = f"Lỗi khi gọi tool '{tool_name}': {e}"

    return result_text, issues_found


def _tool_status_message(tool_name: str, tool_args: Dict) -> str:
    """Generate a user-friendly status message for tool execution."""
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
        msg += "..."
        return msg
    return f"Đang thực hiện: {tool_name}..."


TOOL_CALL_PREFIXES = ("<tool_call>", '{"tool"')
PREFIX_BUFFER_SIZE = 20  # chars — enough to detect "<tool_call>" (11) or '{"tool"' (7)


class StreamResult:
    """Side-channel to pass metadata (issues, errors) out of the stream generator."""
    def __init__(self):
        self.issues: List[Dict] = []
        self.error: Optional[str] = None


@observe(name="agent_solve_issue")
def solve_issue_stream(query: str, history: List[Dict[str, str]] = None,
                       api_key: str = "", result: Optional[StreamResult] = None,
                       session_id: str = None, user_id: str = None):
    """
    Streaming generator yielding event dicts for Streamlit rendering.
    
    Creates ONE Langfuse Trace per query with nested spans.
    
    Langfuse v4: session_id and user_id are propagated via propagate_attributes()
    context manager so all nested @observe calls inherit these attributes.

    Event types:
      {"type": "status", "message": "..."}  — progress indicator for UI
      {"type": "chunk",  "text": "..."}     — text chunk to append to response

    Flow:
      1st LLM call: prefix-buffer (~20 chars) to detect ৩
        → Tool: show status, execute, stream 2nd call with status
        → No tool: flush buffer, stream remaining chunks
    """
    logger.info(f"Processing query (streaming): {query}")
    logger.debug(f"[DEBUG-AGENT] session_id={session_id}, user_id={user_id}")
    history = history or []
    
    # Langfuse v4: propagate session_id and user_id to all nested observations
    propagate_kwargs = {}
    if session_id:
        propagate_kwargs["session_id"] = session_id
    if user_id:
        propagate_kwargs["user_id"] = user_id
    
    logger.debug(f"[DEBUG-AGENT] propagate_kwargs={propagate_kwargs}")
    
    scratchpad = ""
    all_issues = []

    logger.debug(f"[DEBUG-AGENT] Creating LLM instance: model={LLM_MODEL}, temp={LLM_TEMPERATURE}")
    llm = get_company_llm(model=LLM_MODEL, temperature=LLM_TEMPERATURE, api_key=api_key)
    logger.debug(f"[DEBUG-AGENT] LLM instance created: {llm._llm_type}")

    # Langfuse v4: use propagate_attributes context manager so all nested
    # @observe calls (tool_execution, llm_stream, llm_generate) inherit
    # session_id and user_id on their trace.
    # Wrap in try/except so Langfuse connection errors don't crash the agent.
    _use_propagate = bool(propagate_kwargs)
    logger.debug(f"[DEBUG-AGENT] Will use propagate_attributes: {_use_propagate}")
    
    try:
        if _use_propagate:
            logger.debug("[DEBUG-AGENT] Calling propagate_attributes()...")
            _attr_ctx = propagate_attributes(**propagate_kwargs)
            logger.debug(f"[DEBUG-AGENT] propagate_attributes() returned: {_attr_ctx}")
        else:
            _attr_ctx = nullcontext()
            logger.debug("[DEBUG-AGENT] No propagate_kwargs, using nullcontext")
    except Exception as lf_err:
        logger.warning(f"[DEBUG-AGENT] propagate_attributes FAILED: {type(lf_err).__name__}: {lf_err}", exc_info=True)
        _attr_ctx = nullcontext()
    
    logger.debug(f"[DEBUG-AGENT] Entering context manager: {type(_attr_ctx).__name__}")
    with _attr_ctx:
        logger.debug("[DEBUG-AGENT] Inside context manager, starting agent loop")
        try:
            for iteration in range(MAX_ITERATIONS + 1):
                messages = _build_agent_messages(query, history, scratchpad)

                if not scratchpad:
                    # --- First LLM call: prefix-buffer to detect tool calls ---
                    yield {"type": "status", "message": "Đang phân tích câu hỏi..."}

                    prefix = ""
                    prefix_done = False
                    is_tool = False
                    buffer = []  # text strings (not AIMessageChunk)

                    with Timer("LLM streaming call (1st)"):
                        for ai_chunk in llm.stream(messages):
                            text = ai_chunk.content
                            if not text:
                                continue

                            if not prefix_done:
                                prefix += text
                                buffer.append(text)

                                if any(tag in prefix for tag in TOOL_CALL_PREFIXES):
                                    is_tool = True
                                    prefix_done = True
                                elif len(prefix) >= PREFIX_BUFFER_SIZE:
                                    prefix_done = True
                                    for buf_text in buffer:
                                        yield {"type": "chunk", "text": buf_text}
                                    buffer = None
                            elif is_tool:
                                buffer.append(text)
                            else:
                                yield {"type": "chunk", "text": text}

                    # Handle end-of-stream for first call
                    if is_tool:
                        full_text = "".join(buffer)
                        tool_call = parse_tool_call(full_text)
                        if tool_call:
                            tool_name = tool_call.get("tool", "")
                            tool_args = tool_call.get("args", {})
                            logger.info(f"Agent wants tool: {tool_name}({tool_args})")

                            yield {"type": "status", "message": _tool_status_message(tool_name, tool_args)}

                            scratchpad += (
                                f"\n--- Agent goi tool ---\n"
                                f"Tool: {tool_name}\n"
                                f"Args: {json.dumps(tool_args, ensure_ascii=False)}\n"
                            )
                            result_text, issues_found = _execute_tool_sync(tool_call)
                            if issues_found:
                                all_issues = issues_found
                            scratchpad += f"\n--- Tool Result ---\n{result_text}\n"
                            continue  # → next iteration (stream final answer)
                        else:
                            # Tool prefix detected but JSON parse failed — yield as text
                            logger.warning("Tool prefix detected but JSON parse failed, yielding as text")
                            for buf_text in buffer:
                                yield {"type": "chunk", "text": buf_text}
                    elif buffer:
                        # Very short response (< PREFIX_BUFFER_SIZE), not flushed yet
                        for buf_text in buffer:
                            yield {"type": "chunk", "text": buf_text}

                    # Direct answer (or parse failure) — done
                    if result is not None:
                        result.issues = all_issues
                    return

                else:
                    # --- After tools: stream directly (no tool-call re-check) ---
                    yield {"type": "status", "message": "Đang viết câu trả lời..."}

                    with Timer("LLM streaming call (final)"):
                        for ai_chunk in llm.stream(messages):
                            text = ai_chunk.content
                            if text:
                                yield {"type": "chunk", "text": text}

                    if result is not None:
                        result.issues = all_issues
                    return

            # Exhausted iterations
            if result is not None:
                result.issues = all_issues

        except Exception as e:
            logger.error(f"Streaming error: {e}")
            if result is not None:
                result.error = str(e)
