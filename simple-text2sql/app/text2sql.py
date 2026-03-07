"""Simple Text2SQL Pipeline"""

import json
import sqlite3
import re
from typing import List, Dict, Any

from config import DB_PATH, SCHEMA_JSON_PATH
from company_chat_model import get_llm


def load_schema() -> str:
    """Load database schema from JSON file"""
    try:
        with open(SCHEMA_JSON_PATH, "r", encoding="utf-8") as f:
            schema = json.load(f)
        return json.dumps(schema, indent=2, ensure_ascii=False)
    except Exception as e:
        raise FileNotFoundError(f"Cannot load schema: {e}")


def generate_sql(question: str) -> str:
    """Generate SQL from natural language question"""
    schema_context = load_schema()
    llm = get_llm()
    
    prompt = f"""You are a SQL expert. Generate a SQLite query based on the database schema.

Database Schema:
{schema_context}

Question: {question}

Rules:
- Return ONLY the SQL query, no explanation
- Use proper SQLite syntax
- Column and table names must match schema exactly
- For text matching, use LIKE with % for partial matches

SQL:"""

    response = llm.invoke(prompt)
    sql = response.content.strip()
    
    # Clean up markdown code blocks if present
    sql = re.sub(r"```sql\s*", "", sql)
    sql = re.sub(r"```\s*", "", sql)
    sql = sql.strip()
    
    return sql


def execute_sql(sql: str) -> List[Dict[str, Any]]:
    """Execute SQL and return results"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        cursor.execute(sql)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def text2sql(question: str) -> Dict[str, Any]:
    """Main function: question -> SQL -> results"""
    sql = generate_sql(question)
    results = execute_sql(sql)
    return {"question": question, "sql": sql, "results": results, "row_count": len(results)}