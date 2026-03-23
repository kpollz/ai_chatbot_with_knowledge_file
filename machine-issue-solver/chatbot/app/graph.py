"""
LangGraph ReAct Agent for Machine Issue Solver

Architecture: Text-based tool calling (works with any LLM, no native function calling needed)

Flow:
  START -> agent -> (has tool call?) -> YES: tool_node -> agent (loop)
                                     -> NO:  END (return response)

The agent can:
- Answer general questions directly (no tool call)
- Search issues by machine + line via search_issues tool
- List machines / lines for discovery
- Use conversation history to maintain context across turns
"""

from typing import TypedDict, Optional, List, Dict
import json
import re

from langgraph.graph import StateGraph, START, END
from langchain_core.messages import SystemMessage, HumanMessage

from config import LLM_MODEL, LLM_TEMPERATURE
from company_chat_model import get_company_llm
from api_client import (search_issues, list_machines, list_lines,
                        search_issues_sync, list_machines_sync, list_lines_sync)
from history import format_history_for_prompt
from logger import logger, Timer


MAX_ITERATIONS = 3
TOOL_CALL_PATTERN = re.compile(r'<tool_call>(.*?)</tool_call>', re.DOTALL)

SYSTEM_PROMPT = """Ban la "Machine Issue Solver" — tro ly ky thuat chuyen ve cac van de may moc trong nha may.

Nhiem vu cua ban:
- Tra loi cac cau hoi ve van de may moc dua tren du lieu trong co so du lieu
- Tra loi cac cau hoi chung ve ban than va kha nang cua ban
- Su dung lich su hoi thoai de hieu ngu canh (vi du: neu nguoi dung da noi ve Line 2 truoc do, khong can hoi lai)

Ban co the su dung cac tool sau:

1. search_issues(machine_name: str, line_name: str)
   Tim kiem cac van de lien quan den mot may cu the tren mot line cu the.
   Tra ve danh sach cac van de voi trieu chung, nguyen nhan, va giai phap.

2. list_machines()
   Liet ke tat ca cac may co trong co so du lieu.

3. list_lines()
   Liet ke tat ca cac day chuyen san xuat.

Cach su dung tool — bao gom CHINH XAC cu phap nay trong cau tra loi:
<tool_call>{"tool": "search_issues", "args": {"machine_name": "CNC-01", "line_name": "Line 2"}}</tool_call>

Quy tac:
- Chi goi MOT tool moi lan
- Neu khong can tool, tra loi truc tiep (KHONG bao gom <tool_call>)
- Neu nguoi dung hoi cau hoi chung ("Ban la ai?", "Ban lam duoc gi?"), tra loi truc tiep
- Neu thieu thong tin (ten may hoac line), hoi nguoi dung mot cach tu nhien thay vi tu choi
- Su dung lich su hoi thoai de lay thong tin da biet (vi du: neu nguoi dung da noi ve Line 2, dung lai thong tin do)
- Tra loi bang tieng Viet neu nguoi dung dung tieng Viet, tieng Anh neu dung tieng Anh"""


# ---- State ----

class GraphState(TypedDict):
    query: str                              # Current user query
    history: List[Dict[str, str]]           # Conversation history
    api_key: str                            # User-provided LLM API key
    scratchpad: str                         # Agent reasoning + tool results log
    pending_tool_call: Optional[Dict]       # Tool call to execute next
    response: Optional[str]                 # Final response (set when done)
    issues: List[Dict]                      # Issues found (for UI display)
    iterations: int                         # Loop counter
    error: Optional[str]                    # Error message


# ---- Helpers ----

def parse_tool_call(text: str) -> Optional[Dict]:
    """Extract tool call from LLM response text."""
    match = TOOL_CALL_PATTERN.search(text)
    if not match:
        return None
    try:
        tool_call = json.loads(match.group(1).strip())
        if "tool" in tool_call:
            return tool_call
        return None
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse tool call JSON: {match.group(1)}")
        return None


def clean_response(text: str) -> str:
    """Remove <tool_call> tags and clean up the response text."""
    cleaned = TOOL_CALL_PATTERN.sub("", text).strip()
    return cleaned


def format_issues_for_scratchpad(issues: List[Dict]) -> str:
    """Format issue list as readable text for the agent scratchpad."""
    if not issues:
        return "Khong tim thay van de nao."

    lines = [f"Tim thay {len(issues)} van de:\n"]
    for i, issue in enumerate(issues, 1):
        lines.append(f"Van de {i}:")
        lines.append(f"  Ngay: {issue.get('Date', 'N/A')}")
        lines.append(f"  Hien tuong (Symptom): {issue.get('hien_tuong', 'N/A')}")
        lines.append(f"  Nguyen nhan (Cause): {issue.get('nguyen_nhan', 'N/A')}")
        lines.append(f"  Khac phuc (Solution): {issue.get('khac_phuc', 'N/A')}")
        lines.append(f"  PIC: {issue.get('PIC', 'N/A')}")
        lines.append("")
    return "\n".join(lines)


# ---- Nodes ----

async def agent_node(state: GraphState) -> dict:
    """LLM agent: reasons about the query and optionally calls a tool."""
    iteration = state.get("iterations", 0)
    logger.info(f"Node: agent (iteration {iteration})")

    query = state["query"]
    history = state.get("history", [])
    scratchpad = state.get("scratchpad", "")

    # Build user prompt
    parts = []

    # Conversation history
    history_text = format_history_for_prompt(history)
    if history_text:
        parts.append(history_text)

    # Current query
    parts.append(f"Cau hoi hien tai cua nguoi dung: {query}")

    # Scratchpad with tool results from previous iterations
    if scratchpad:
        parts.append(
            f"\n{scratchpad}\n"
            "Dua tren ket qua tool o tren, hay tra loi nguoi dung chi tiet va huu ich. "
            "KHONG goi them tool neu khong can thiet."
        )

    user_prompt = "\n\n".join(parts)

    llm = get_company_llm(model=LLM_MODEL, temperature=LLM_TEMPERATURE, api_key=state.get("api_key"))

    try:
        with Timer("LLM agent call"):
            response = await llm.ainvoke([
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=user_prompt),
            ])

        response_text = response.content.strip()
        logger.info(f"Agent response: {len(response_text)} chars")

        # Check for tool call
        tool_call = parse_tool_call(response_text)

        if tool_call:
            tool_name = tool_call.get("tool", "")
            tool_args = tool_call.get("args", {})
            logger.info(f"Agent wants tool: {tool_name}({tool_args})")

            new_scratchpad = (
                scratchpad
                + f"\n--- Agent goi tool ---\n"
                f"Tool: {tool_name}\n"
                f"Args: {json.dumps(tool_args, ensure_ascii=False)}\n"
            )

            return {
                "scratchpad": new_scratchpad,
                "pending_tool_call": tool_call,
            }
        else:
            # Final response — no tool call
            final = clean_response(response_text)
            logger.info("Agent produced final response")
            return {"response": final, "pending_tool_call": None}

    except Exception as e:
        logger.error(f"Agent error: {e}")
        return {"error": str(e)}


async def tool_node(state: GraphState) -> dict:
    """Execute the pending tool call and append results to scratchpad."""
    logger.info("Node: tool_node")

    tool_call = state.get("pending_tool_call")
    scratchpad = state.get("scratchpad", "")

    if not tool_call:
        logger.warning("tool_node called but no pending tool call")
        return {
            "scratchpad": scratchpad + "\n--- Tool Result ---\nError: no tool call found\n",
            "pending_tool_call": None,
            "iterations": state.get("iterations", 0) + 1,
        }

    tool_name = tool_call.get("tool", "")
    tool_args = tool_call.get("args", {})
    result_text = ""
    issues_found = []

    try:
        if tool_name == "search_issues":
            machine_name = tool_args.get("machine_name", "")
            line_name = tool_args.get("line_name", "")

            with Timer(f"Tool: search_issues({machine_name}, {line_name})"):
                issues = await search_issues(machine_name, line_name)

            issues_found = issues
            if not issues:
                result_text = (
                    f"Khong tim thay van de nao cho may '{machine_name}' "
                    f"tren line '{line_name}'."
                )
            else:
                result_text = format_issues_for_scratchpad(issues)

        elif tool_name == "list_machines":
            with Timer("Tool: list_machines"):
                machines = await list_machines()

            if not machines:
                result_text = "Khong co may nao trong co so du lieu."
            else:
                items = [f"Co {len(machines)} may:\n"]
                for m in machines:
                    items.append(f"- {m.get('MachineName', 'N/A')} (ID: {m.get('MachineID', 'N/A')})")
                result_text = "\n".join(items)

        elif tool_name == "list_lines":
            with Timer("Tool: list_lines"):
                lines_data = await list_lines()

            if not lines_data:
                result_text = "Khong co line nao trong co so du lieu."
            else:
                items = [f"Co {len(lines_data)} line:\n"]
                for ln in lines_data:
                    items.append(f"- {ln.get('LineName', 'N/A')} (ID: {ln.get('LineID', 'N/A')})")
                result_text = "\n".join(items)

        else:
            result_text = f"Tool '{tool_name}' khong ton tai. Cac tool kha dung: search_issues, list_machines, list_lines."

    except Exception as e:
        logger.error(f"Tool execution error: {e}")
        result_text = f"Loi khi goi tool '{tool_name}': {e}"

    new_scratchpad = scratchpad + f"\n--- Tool Result ---\n{result_text}\n"

    return {
        "scratchpad": new_scratchpad,
        "pending_tool_call": None,
        "issues": issues_found if issues_found else state.get("issues", []),
        "iterations": state.get("iterations", 0) + 1,
    }


# ---- Routing ----

def route_after_agent(state: GraphState) -> str:
    """Route: response set → END, pending tool → tool_node, max iterations → END."""
    if state.get("response") is not None:
        return END
    if state.get("error") and not state.get("pending_tool_call"):
        return END
    if state.get("iterations", 0) >= MAX_ITERATIONS:
        logger.warning("Max iterations reached")
        return END
    if state.get("pending_tool_call"):
        return "tool_node"
    # Fallback: no response and no tool call — shouldn't happen
    return END


# ---- Build Graph ----

def build_graph():
    """Build and compile the ReAct agent graph."""
    graph = StateGraph(GraphState)

    graph.add_node("agent", agent_node)
    graph.add_node("tool_node", tool_node)

    graph.add_edge(START, "agent")
    graph.add_conditional_edges(
        "agent",
        route_after_agent,
        {"tool_node": "tool_node", END: END},
    )
    graph.add_edge("tool_node", "agent")  # Loop back

    return graph.compile()


# Global graph instance
app_graph = build_graph()


async def solve_issue(query: str, history: List[Dict[str, str]] = None, api_key: str = "") -> dict:
    """
    Main entry point — process a user query through the ReAct agent (non-streaming).

    Args:
        query: User's question
        history: Conversation history [{"role": "user"/"assistant", "content": "..."}]
        api_key: User-provided LLM API key

    Returns:
        dict with response, issues, error
    """
    logger.info(f"Processing query: {query}")

    initial_state = {
        "query": query,
        "history": history or [],
        "api_key": api_key,
        "scratchpad": "",
        "pending_tool_call": None,
        "response": None,
        "issues": [],
        "iterations": 0,
        "error": None,
    }

    result = await app_graph.ainvoke(initial_state)

    # Safety: if agent loop ended without response
    if result.get("response") is None and not result.get("error"):
        result["error"] = "Agent could not generate a response. Please try again."

    return result


# ---- Streaming entry point (sync generator) ----

def _build_agent_messages(query: str, history: List[Dict[str, str]],
                          scratchpad: str) -> list:
    """Build LLM messages for agent call (shared logic with agent_node)."""
    from langchain_core.messages import SystemMessage, HumanMessage
    parts = []
    history_text = format_history_for_prompt(history)
    if history_text:
        parts.append(history_text)
    parts.append(f"Cau hoi hien tai cua nguoi dung: {query}")
    if scratchpad:
        parts.append(
            f"\n{scratchpad}\n"
            "Dua tren ket qua tool o tren, hay tra loi nguoi dung chi tiet va huu ich. "
            "KHONG goi them tool neu khong can thiet."
        )
    user_prompt = "\n\n".join(parts)
    return [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=user_prompt)]


def _execute_tool_sync(tool_call: Dict, issues_list: list) -> tuple:
    """Execute a tool call synchronously. Returns (result_text, issues_found)."""
    tool_name = tool_call.get("tool", "")
    tool_args = tool_call.get("args", {})
    result_text = ""
    issues_found = []

    try:
        if tool_name == "search_issues":
            machine_name = tool_args.get("machine_name", "")
            line_name = tool_args.get("line_name", "")
            logger.info(f"Tool (sync): search_issues({machine_name}, {line_name})")
            issues = search_issues_sync(machine_name, line_name)
            issues_found = issues
            if not issues:
                result_text = (f"Khong tim thay van de nao cho may '{machine_name}' "
                               f"tren line '{line_name}'.")
            else:
                result_text = format_issues_for_scratchpad(issues)

        elif tool_name == "list_machines":
            logger.info("Tool (sync): list_machines")
            machines = list_machines_sync()
            if not machines:
                result_text = "Khong co may nao trong co so du lieu."
            else:
                items = [f"Co {len(machines)} may:\n"]
                for m in machines:
                    items.append(f"- {m.get('MachineName', 'N/A')} (ID: {m.get('MachineID', 'N/A')})")
                result_text = "\n".join(items)

        elif tool_name == "list_lines":
            logger.info("Tool (sync): list_lines")
            lines_data = list_lines_sync()
            if not lines_data:
                result_text = "Khong co line nao trong co so du lieu."
            else:
                items = [f"Co {len(lines_data)} line:\n"]
                for ln in lines_data:
                    items.append(f"- {ln.get('LineName', 'N/A')} (ID: {ln.get('LineID', 'N/A')})")
                result_text = "\n".join(items)
        else:
            result_text = f"Tool '{tool_name}' khong ton tai."

    except Exception as e:
        logger.error(f"Tool execution error: {e}")
        result_text = f"Loi khi goi tool '{tool_name}': {e}"

    return result_text, issues_found


def solve_issue_stream(query: str, history: List[Dict[str, str]] = None,
                       api_key: str = ""):
    """
    Streaming entry point — sync generator yielding (event_type, data) tuples.

    Event types:
        ("status", message)  — status update (e.g., tool search in progress)
        ("token", text)      — streaming text chunk
        ("done", issues)     — final signal with issues list

    Strategy:
        - 1st LLM call: stream to buffer, check for tool call
          - If tool call → execute tools, then stream 2nd call directly to user
          - If no tool call → replay buffer (direct answer, usually short)
        - After tools: stream directly to user (real streaming for long responses)
    """
    logger.info(f"Processing query (streaming): {query}")
    history = history or []
    scratchpad = ""
    issues = []

    llm = get_company_llm(model=LLM_MODEL, temperature=LLM_TEMPERATURE, api_key=api_key)

    try:
        for iteration in range(MAX_ITERATIONS + 1):
            messages = _build_agent_messages(query, history, scratchpad)

            if not scratchpad:
                # First call — buffer to detect tool calls
                chunks = []
                for chunk in llm.stream_chat(messages):
                    chunks.append(chunk)

                full_text = "".join(chunks)
                tool_call = parse_tool_call(full_text)

                if tool_call:
                    tool_name = tool_call.get("tool", "")
                    tool_args = tool_call.get("args", {})
                    logger.info(f"Agent wants tool (stream): {tool_name}({tool_args})")

                    yield ("status", f"Dang tim kiem thong tin...")

                    scratchpad += (
                        f"\n--- Agent goi tool ---\n"
                        f"Tool: {tool_name}\n"
                        f"Args: {json.dumps(tool_args, ensure_ascii=False)}\n"
                    )
                    result_text, issues_found = _execute_tool_sync(tool_call, issues)
                    if issues_found:
                        issues = issues_found
                    scratchpad += f"\n--- Tool Result ---\n{result_text}\n"
                    continue
                else:
                    # Direct answer — replay buffered chunks
                    cleaned = clean_response(full_text)
                    for chunk in chunks:
                        cleaned_chunk = clean_response(chunk)
                        if cleaned_chunk:
                            yield ("token", cleaned_chunk)
                    yield ("done", issues)
                    return
            else:
                # After tools — stream directly to user (real streaming!)
                full_text = ""
                for chunk in llm.stream_chat(messages):
                    full_text += chunk
                    yield ("token", chunk)

                # Edge case: unexpected additional tool call
                tool_call = parse_tool_call(full_text)
                if tool_call and iteration < MAX_ITERATIONS:
                    tool_name = tool_call.get("tool", "")
                    tool_args = tool_call.get("args", {})
                    logger.warning(f"Unexpected tool call during streaming: {tool_name}")
                    yield ("status", f"\nDang tim kiem them...")

                    scratchpad += (
                        f"\n--- Agent goi tool ---\n"
                        f"Tool: {tool_name}\n"
                        f"Args: {json.dumps(tool_args, ensure_ascii=False)}\n"
                    )
                    result_text, issues_found = _execute_tool_sync(tool_call, issues)
                    if issues_found:
                        issues = issues_found
                    scratchpad += f"\n--- Tool Result ---\n{result_text}\n"
                    continue

                yield ("done", issues)
                return

        # Exhausted iterations
        yield ("done", issues)

    except Exception as e:
        logger.error(f"Streaming error: {e}")
        yield ("error", str(e))
