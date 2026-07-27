"""Machine Issue Solver — the prompt and the tools.

``agent.py`` composes these into a ``create_react_agent`` graph; ``main.py``
serves it. Tool results reach the client as AG-UI tool events, so nothing here
needs a side-channel to carry them out of the run.
"""

from typing import Optional, List, Dict

from langchain_core.tools import tool

from api_client import search_issues_sync
from logger import logger, Timer

# Max tool-using steps before LangGraph stops. main.py turns this into the run's
# recursion_limit (2*N + 1: each step is a model call plus a tool call).
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

    if not issues:
        desc = f"máy '{machine_name}' trên line '{line_name}'"
        if location:
            desc += f" tại Location '{location}'"
        if serial:
            desc += f" với Serial '{serial}'"
        return f"Không tìm thấy vấn đề nào cho {desc}."
    return format_issues_for_scratchpad(issues)


TOOLS = [search_issues]
