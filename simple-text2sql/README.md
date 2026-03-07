# 🔍 Simple Text2SQL

A minimal Text2SQL application that converts natural language to SQL queries.

## Features

- No file upload needed - uses existing SQLite database
- JSON schema file describes database for LLM context
- Simple chat interface
- Shows generated SQL and results

## Quick Start

```bash
cd simple-text2sql
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your LLM credentials
# Place your database.db and schema.json in database/
streamlit run app/streamlit_app.py
```

## Project Structure

```
simple-text2sql/
├── app/
│   ├── config.py              # Configuration
│   ├── company_chat_model.py  # LLM wrapper
│   ├── text2sql.py            # Core logic
│   └── streamlit_app.py       # UI
├── database/
│   ├── data.db                # Your SQLite database
│   └── schema.json            # Database schema for LLM
├── .env.example
├── requirements.txt
└── README.md
```

## Schema JSON Format

Create `database/schema.json` to describe your database:

```json
{
  "tables": [
    {
      "name": "employees",
      "columns": [
        {"name": "id", "type": "INTEGER", "description": "Employee ID"},
        {"name": "name", "type": "TEXT", "description": "Full name"},
        {"name": "department", "type": "TEXT", "description": "Department name"},
        {"name": "salary", "type": "REAL", "description": "Monthly salary"}
      ]
    }
  ]
}
```

## Example Questions

- "Show all employees"
- "What is the average salary by department?"
- "Find employees in IT department"
- "Who has the highest salary?"