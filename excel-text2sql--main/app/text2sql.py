"""
Text2SQL Pipeline for Excel Files

This module handles:
1. Loading Excel files into SQLite database
2. Generating SQL queries from natural language
3. Executing queries and returning results
"""

import os
import sqlite3
import pandas as pd
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

from config import DB_PATH, TABLE_NAME
from llm_provider import get_llm


class Text2SQLPipeline:
    """
    Text2SQL Pipeline that converts natural language to SQL queries.
    
    Flow:
    1. Upload Excel file → Store in SQLite database
    2. User asks question → LLM generates SQL query
    3. Execute SQL → Return results with natural language answer
    """
    
    def __init__(self):
        self.connection: Optional[sqlite3.Connection] = None
        self.schema_info: Optional[str] = None
        self.llm = None
        self.table_name = TABLE_NAME
    
    def initialize(self):
        """Initialize the LLM."""
        if self.llm is None:
            self.llm = get_llm()
    
    def load_excel_to_db(self, file_path: str, table_name: str = None) -> Tuple[bool, str, int]:
        """
        Load an Excel file into SQLite database.
        
        Args:
            file_path: Path to the Excel file
            table_name: Name of the table (default: from config)
            
        Returns:
            Tuple of (success, message, row_count)
        """
        try:
            # Read Excel file
            df = pd.read_excel(file_path)
            
            # Clean column names (replace spaces with underscores)
            df.columns = [col.strip().replace(' ', '_') for col in df.columns]
            
            # Try to convert date columns
            for col in df.columns:
                if 'date' in col.lower():
                    try:
                        df[col] = pd.to_datetime(df[col], dayfirst=True)
                    except:
                        pass
            
            # Create database directory if needed
            db_dir = Path(DB_PATH).parent
            db_dir.mkdir(parents=True, exist_ok=True)
            
            # Create connection
            self.connection = sqlite3.connect(DB_PATH)
            
            # Store table name
            self.table_name = table_name or TABLE_NAME
            
            # Write to SQLite
            df.to_sql(self.table_name, self.connection, if_exists='replace', index=False)
            
            # Generate schema info
            self._generate_schema_info(df)
            
            return True, f"Loaded {len(df)} rows into table '{self.table_name}'", len(df)
            
        except Exception as e:
            return False, f"Error loading file: {str(e)}", 0
    
    def _generate_schema_info(self, df: pd.DataFrame):
        """Generate schema information for the LLM."""
        columns_info = []
        
        for col in df.columns:
            dtype = str(df[col].dtype)
            
            # Map pandas dtypes to SQL-like types
            if 'int' in dtype:
                sql_type = 'int'
            elif 'float' in dtype:
                sql_type = 'float'
            elif 'datetime' in dtype:
                sql_type = 'datetime'
            elif 'date' in dtype:
                sql_type = 'date'
            else:
                sql_type = 'string'
            
            # Get sample values for better context
            sample_values = df[col].dropna().head(3).tolist()
            sample_str = ', '.join([str(v)[:30] for v in sample_values[:3]])
            
            columns_info.append({
                'name': col,
                'type': sql_type,
                'sample': sample_str
            })
        
        # Build schema JSON
        schema_lines = []
        for col in columns_info:
            schema_lines.append(f"            {{'name': '{col['name']}', 'type': '{col['type']}', 'sample_values': '{col['sample']}'}}")
        
        self.schema_info = f"""[
    {{
        'table': '{self.table_name}',
        'columns': [
{chr(10).join(schema_lines)}
        ]
    }}
]"""
    
    def get_schema_info(self) -> str:
        """Get the current database schema info."""
        return self.schema_info or "No database loaded"
    
    def execute_sql(self, query: str) -> Tuple[List[Dict], str]:
        """
        Execute a SQL query and return results.
        
        Args:
            query: SQL SELECT query
            
        Returns:
            Tuple of (results as list of dicts, error message if any)
        """
        if not self.connection:
            return [], "No database connection. Please upload an Excel file first."
        
        try:
            # Only allow SELECT queries for safety
            query_upper = query.strip().upper()
            if not query_upper.startswith('SELECT'):
                return [], "Only SELECT queries are allowed."
            
            df = pd.read_sql_query(query, self.connection)
            results = df.to_dict(orient='records')
            return results, ""
            
        except Exception as e:
            return [], f"SQL Error: {str(e)}"
    
    def generate_sql(self, question: str) -> str:
        """
        Generate SQL query from natural language question.
        
        Args:
            question: Natural language question
            
        Returns:
            SQL query string
        """
        self.initialize()
        
        prompt = f"""You are an expert SQL analyst. Generate a SQL query based on the user question and the database schema.

IMPORTANT RULES:
1. Only generate SELECT queries
2. Use the exact column names from the schema
3. Return ONLY the SQL query, nothing else
4. Do not use markdown formatting
5. The table name is: {self.table_name}

Database Schema:
{self.schema_info}

User Question: {question}

Generate a SQL query for the user's question. Return ONLY the SQL, no explanation."""

        from langchain_core.messages import HumanMessage
        
        messages = [HumanMessage(content=prompt)]
        
        response = self.llm.invoke(messages)
        sql_query = response.content.strip()
        
        # Clean up the SQL query
        sql_query = sql_query.replace('```sql', '').replace('```', '').strip()
        
        return sql_query
    
    def answer(self, question: str) -> Dict[str, Any]:
        """
        Answer a natural language question using Text2SQL.
        
        Args:
            question: Natural language question
            
        Returns:
            Dict with answer, sql_query, and results
        """
        self.initialize()
        
        if not self.connection:
            return {
                "answer": "Please upload an Excel file first.",
                "sql_query": "",
                "results": [],
                "error": "No database connection"
            }
        
        try:
            # Generate SQL query
            sql_query = self.generate_sql(question)
            
            # Execute query
            results, error = self.execute_sql(sql_query)
            
            if error:
                return {
                    "answer": f"Error executing query: {error}",
                    "sql_query": sql_query,
                    "results": [],
                    "error": error
                }
            
            # Generate natural language answer from results
            answer = self._generate_answer(question, sql_query, results)
            
            return {
                "answer": answer,
                "sql_query": sql_query,
                "results": results,
                "error": ""
            }
            
        except Exception as e:
            return {
                "answer": f"Error: {str(e)}",
                "sql_query": "",
                "results": [],
                "error": str(e)
            }
    
    def _generate_answer(self, question: str, sql_query: str, results: List[Dict]) -> str:
        """Generate natural language answer from SQL results."""
        
        # Format results for the LLM
        if not results:
            return "No results found for your query."
        
        results_str = str(results[:10])  # Limit to first 10 results
        
        prompt = f"""Based on the following SQL query results, provide a clear and concise answer to the user's question.

Question: {question}

SQL Query: {sql_query}

Results (first 10 rows): {results_str}

Provide a natural language answer based on these results. Be concise and informative."""

        from langchain_core.messages import HumanMessage
        
        messages = [HumanMessage(content=prompt)]
        
        response = self.llm.invoke(messages)
        return response.content
    
    def close(self):
        """Close the database connection."""
        if self.connection:
            self.connection.close()
            self.connection = None