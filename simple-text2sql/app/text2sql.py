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


def text2sql(question: str) -> Dict[str, Any]:
    """Main function: question -> SQL -> results"""
    logger.info(f"Processing question: {question}")
    
    try:
        sql = generate_sql(question)
        results = execute_sql(sql)
        
        logger.info(f"text2sql completed successfully")
        return {
            "question": question,
            "sql": sql,
            "results": results,
            "row_count": len(results),
            "error": None
        }
    except Exception as e:
        logger.error(f"text2sql failed: {e}")
        return {
            "question": question,
            "sql": None,
            "results": [],
            "row_count": 0,
            "error": str(e)
        }