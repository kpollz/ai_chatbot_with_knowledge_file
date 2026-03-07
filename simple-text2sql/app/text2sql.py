"""Simple Text2SQL Pipeline"""

import json
import sqlite3
import re
from typing import List, Dict, Any

from config import DB_PATH, SCHEMA_JSON_PATH
from company_chat_model import get_llm
from logger import logger, Timer


def load_schema() -> str:
    """Load database schema from JSON file"""
    logger.info(f"Loading schema from {SCHEMA_JSON_PATH}")
    try:
        with open(SCHEMA_JSON_PATH, "r", encoding="utf-8") as f:
            schema = json.load(f)
        schema_str = json.dumps(schema, indent=2, ensure_ascii=False)
        logger.info(f"Schema loaded: {len(schema_str)} chars")
        return schema_str
    except Exception as e:
        logger.error(f"Failed to load schema: {e}")
        raise FileNotFoundError(f"Cannot load schema: {e}")


def generate_sql(question: str) -> str:
    """Generate SQL from natural language question"""
    from langchain_core.messages import HumanMessage, SystemMessage
    
    logger.info(f"Generating SQL for: {question[:50]}...")
    
    schema_context = load_schema()
    llm = get_llm()
    
    # System prompt - defines behavior
    system_prompt = f"""You are a SQL expert. Generate SQLite queries based on the database schema.

Database Schema:
{schema_context}

Rules:
- Return ONLY the SQL query, no explanation
- Use proper SQLite syntax
- Column and table names must match schema exactly
- For text matching, use LIKE with % for partial matches"""

    # User prompt - the question
    user_prompt = f"Question: {question}\n\nSQL:"

    # Use SystemMessage and HumanMessage together
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt)
    ]

    with Timer("LLM SQL generation"):
        response = llm.invoke(messages)
    
    sql = response.content.strip()
    
    # Clean up markdown code blocks if present
    sql = re.sub(r"```sql\s*", "", sql)
    sql = re.sub(r"```\s*", "", sql)
    sql = sql.strip()
    
    logger.info(f"Generated SQL: {sql[:100]}...")
    return sql


def execute_sql(sql: str) -> List[Dict[str, Any]]:
    """Execute SQL and return results"""
    logger.info(f"Executing SQL on {DB_PATH}")
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        with Timer("SQL execution"):
            cursor.execute(sql)
            rows = cursor.fetchall()
        
        results = [dict(row) for row in rows]
        logger.info(f"Query returned {len(results)} rows")
        return results
    except Exception as e:
        logger.error(f"SQL execution failed: {e}")
        raise
    finally:
        conn.close()


def generate_answer(question: str, sql: str, results: List[Dict[str, Any]]) -> str:
    """Generate natural language answer from SQL results"""
    from langchain_core.messages import HumanMessage, SystemMessage
    
    logger.info("Generating natural language answer...")
    
    if not results:
        return "No results found for your query."
    
    llm = get_llm()
    
    # Format results for LLM (limit to first 10 rows)
    results_str = str(results[:10])
    
    system_prompt = """You are a helpful data analyst. Based on the SQL query results, provide a clear and concise answer to the user's question.
- Be informative but concise
- Summarize the key findings
- Use natural language, not technical jargon"""

    user_prompt = f"""Question: {question}

SQL Query: {sql}

Results (first 10 rows): {results_str}

Provide a natural language answer based on these results:"""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt)
    ]

    with Timer("LLM answer generation"):
        response = llm.invoke(messages)
    
    answer = response.content.strip()
    logger.info(f"Answer generated: {answer[:100]}...")
    return answer


def text2sql(question: str) -> Dict[str, Any]:
    """Main function: question -> SQL -> results -> answer"""
    logger.info(f"Processing question: {question}")
    
    try:
        # Step 1: Generate SQL
        sql = generate_sql(question)
        
        # Step 2: Execute SQL
        results = execute_sql(sql)
        
        # Step 3: Generate natural language answer
        answer = generate_answer(question, sql, results)
        
        logger.info("text2sql completed successfully")
        return {
            "question": question,
            "sql": sql,
            "results": results,
            "row_count": len(results),
            "answer": answer,
            "error": None
        }
    except Exception as e:
        logger.error(f"text2sql failed: {e}")
        return {
            "question": question,
            "sql": None,
            "results": [],
            "row_count": 0,
            "answer": None,
            "error": str(e)
        }