"""
LangGraph Workflow for Machine Issue Solver

Workflow:
1. extract_info: Extract machine_name and line_number from user query
2. check_info: Check if we have enough information (conditional)
3. query_database: Query SQL database for issues
4. generate_solution: Use LLM to generate solution from retrieved issues
"""

from typing import TypedDict, Optional, List, Dict, Annotated
import operator
import sqlite3
import json

from langgraph.graph import StateGraph, START, END

from config import DB_PATH, LLM_MODEL, LLM_TEMPERATURE
from company_chat_model import get_company_llm
from logger import logger, Timer


# ---- State Definition ----
class GraphState(TypedDict):
    """State that flows through the graph"""
    query: str  # Original user query
    machine_name: Optional[str]  # Extracted machine name
    line_number: Optional[str]  # Extracted line number
    has_enough_info: bool  # Whether we have enough info
    rejection_reason: Optional[str]  # Reason for rejection
    issues: List[Dict]  # Retrieved issues from database
    solution: Optional[str]  # Generated solution
    error: Optional[str]  # Any error message


# ---- Database Operations ----
def query_machine_issues(machine_name: str, line_number: str) -> List[Dict]:
    """Query database for issues belonging to a specific machine"""
    query = """
        SELECT i.MachineID, i."Hien tuong", i."Nguyen nhan", i."Khac phuc",
               m.MachineName, l.LineName
        FROM Issues i
        JOIN Machines m ON i.MachineID = m.MachineID
        JOIN Teams t ON m.TeamID = t.TeamID
        JOIN Lines l ON t.LineID = l.LineID
        WHERE m.MachineName = ? AND l.LineName = ?
    """
    
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(query, (machine_name, line_number))
        rows = cursor.fetchall()
        conn.close()
        
        issues = [dict(row) for row in rows]
        logger.info(f"Found {len(issues)} issues for machine '{machine_name}' on line '{line_number}'")
        return issues
    except Exception as e:
        logger.error(f"Database error: {e}")
        return []


# ---- Node Functions ----
def extract_info_node(state: GraphState) -> dict:
    """Extract machine_name and line_number from user query using LLM"""
    logger.info("Node: extract_info")
    
    query = state["query"]
    
    # Create LLM instance
    llm = get_company_llm(model=LLM_MODEL, temperature=LLM_TEMPERATURE)
    
    extraction_prompt = f"""You are an information extraction assistant. Extract the following from the user's query:
1. machine_name: The name of the machine (e.g., "Machine A", "CNC-01", "Robot Arm")
2. line_number: The production line number or name (e.g., "Line 1", "L2", "Production Line A")

User query: {query}

IMPORTANT:
- If the query mentions a specific machine name, extract it exactly as mentioned
- If the query mentions a line number/name, extract it exactly as mentioned
- Return ONLY a JSON object with no additional text

Return JSON in this exact format:
{{"machine_name": "extracted name or null", "line_number": "extracted number or null"}}"""

    try:
        with Timer("LLM extraction"):
            response = llm.invoke(extraction_prompt)
        
        result_text = response.content.strip()
        # Try to parse JSON from response
        try:
            # Find JSON in response
            start = result_text.find('{')
            end = result_text.rfind('}') + 1
            if start != -1 and end > start:
                json_str = result_text[start:end]
                extracted = json.loads(json_str)
            else:
                extracted = {"machine_name": None, "line_number": None}
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse JSON from LLM response: {result_text}")
            extracted = {"machine_name": None, "line_number": None}
        
        machine_name = extracted.get("machine_name")
        line_number = extracted.get("line_number")
        
        logger.info(f"Extracted - machine_name: {machine_name}, line_number: {line_number}")
        
        return {
            "machine_name": machine_name,
            "line_number": line_number
        }
    
    except Exception as e:
        logger.error(f"Extraction error: {e}")
        return {
            "machine_name": None,
            "line_number": None,
            "error": str(e)
        }


def check_info_node(state: GraphState) -> dict:
    """Check if we have enough information to proceed"""
    logger.info("Node: check_info")
    
    machine_name = state.get("machine_name")
    line_number = state.get("line_number")
    
    has_enough = machine_name is not None and line_number is not None
    has_enough = has_enough and machine_name.lower() != "null" and line_number.lower() != "null"
    
    if not has_enough:
        missing = []
        if not machine_name or machine_name.lower() == "null":
            missing.append("machine name")
        if not line_number or line_number.lower() == "null":
            missing.append("line number")
        
        reason = f"Cannot proceed. Missing: {', '.join(missing)}. Please provide both machine name and line number."
        logger.warning(reason)
        return {
            "has_enough_info": False,
            "rejection_reason": reason
        }
    
    logger.info(f"Info check passed - machine: {machine_name}, line: {line_number}")
    return {
        "has_enough_info": True,
        "rejection_reason": None
    }


def query_database_node(state: GraphState) -> dict:
    """Query the database for issues"""
    logger.info("Node: query_database")
    
    machine_name = state["machine_name"]
    line_number = state["line_number"]
    
    with Timer("Database query"):
        issues = query_machine_issues(machine_name, line_number)
    
    if not issues:
        return {
            "issues": [],
            "error": f"No issues found for machine '{machine_name}' on line '{line_number}'"
        }
    
    return {"issues": issues}


def generate_solution_node(state: GraphState) -> dict:
    """Generate solution using LLM based on retrieved issues"""
    logger.info("Node: generate_solution")
    
    query = state["query"]
    issues = state["issues"]
    machine_name = state["machine_name"]
    line_number = state["line_number"]
    
    # Format issues as context
    context_lines = []
    for i, issue in enumerate(issues, 1):
        context_lines.append(f"""
Issue {i}:
- Hiện tượng (Symptom): {issue.get('Hien tuong', 'N/A')}
- Nguyên nhân (Cause): {issue.get('Nguyen nhan', 'N/A')}
- Khắc phục (Solution): {issue.get('Khac phuc', 'N/A')}
""")
    context = "\n".join(context_lines)
    
    # Create LLM instance
    llm = get_company_llm(model=LLM_MODEL, temperature=LLM_TEMPERATURE)
    
    solution_prompt = f"""Bạn là một chuyên gia kỹ thuật. Dựa trên các vấn đề đã biết của máy, hãy trả lời câu hỏi của người dùng.

Thông tin máy:
- Tên máy: {machine_name}
- Dây chuyền: {line_number}

Các vấn đề đã biết trong cơ sở dữ liệu:
{context}

Câu hỏi của người dùng: {query}

Hãy trả lời một cách chi tiết và hữu ích. Nếu câu hỏi liên quan đến một vấn đề cụ thể, hãy cung cấp:
1. Nguyên nhân có thể có
2. Cách khắc phục
3. Các lưu ý quan trọng

Trả lời bằng tiếng Việt:"""

    try:
        with Timer("LLM solution generation"):
            response = llm.invoke(solution_prompt)
        
        solution = response.content
        logger.info("Solution generated successfully")
        
        return {"solution": solution}
    
    except Exception as e:
        logger.error(f"Solution generation error: {e}")
        return {"solution": None, "error": str(e)}


# ---- Routing Functions ----
def route_after_check(state: GraphState) -> str:
    """Route based on whether we have enough info"""
    if state.get("has_enough_info"):
        return "query_database"
    else:
        return END


# ---- Build Graph ----
def build_graph():
    """Build and compile the LangGraph workflow"""
    
    # Create the graph
    graph = StateGraph(GraphState)
    
    # Add nodes
    graph.add_node("extract_info", extract_info_node)
    graph.add_node("check_info", check_info_node)
    graph.add_node("query_database", query_database_node)
    graph.add_node("generate_solution", generate_solution_node)
    
    # Add edges
    graph.add_edge(START, "extract_info")
    graph.add_edge("extract_info", "check_info")
    graph.add_conditional_edges(
        "check_info",
        route_after_check,
        {
            "query_database": "query_database",
            END: END
        }
    )
    graph.add_edge("query_database", "generate_solution")
    graph.add_edge("generate_solution", END)
    
    # Compile
    return graph.compile()


# Create global graph instance
app_graph = build_graph()


def solve_issue(query: str) -> dict:
    """
    Main entry point to solve a machine issue.
    
    Args:
        query: User's question about a machine issue
        
    Returns:
        dict with solution and metadata
    """
    logger.info(f"Processing query: {query}")
    
    initial_state = {
        "query": query,
        "machine_name": None,
        "line_number": None,
        "has_enough_info": False,
        "rejection_reason": None,
        "issues": [],
        "solution": None,
        "error": None
    }
    
    result = app_graph.invoke(initial_state)
    
    return result


if __name__ == "__main__":
    # Test the graph
    test_query = "Tôi cần giải pháp cho máy CNC-01 trên Line 2"
    result = solve_issue(test_query)
    print("\n=== RESULT ===")
    print(f"Machine: {result.get('machine_name')}")
    print(f"Line: {result.get('line_number')}")
    print(f"Issues found: {len(result.get('issues', []))}")
    if result.get('solution'):
        print(f"\nSolution:\n{result['solution']}")
    if result.get('rejection_reason'):
        print(f"Rejection: {result['rejection_reason']}")