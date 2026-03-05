# 📊 Text2SQL - Excel Query System

A Streamlit application that converts natural language questions into SQL queries for Excel data.

## 🔍 What is Text2SQL?

Text2SQL is different from RAG (Retrieval-Augmented Generation):
- **RAG**: Best for unstructured text (PDFs, documents) - uses vector search
- **Text2SQL**: Best for structured data (Excel, databases) - uses SQL queries

## 🚀 How It Works

1. **Upload** an Excel file (.xlsx, .xls)
2. Data is automatically stored in a **SQLite** database
3. Ask questions in **natural language**
4. LLM generates **SQL queries** based on your schema
5. Get **instant answers** with the executed query

## 📋 Features

- 📤 Upload Excel files
- 🗃️ Automatic schema detection
- 💬 Natural language queries
- 🔍 View generated SQL
- 📊 See raw query results
- 🔄 Chat history

## ⚡ Quickstart

```bash
# Navigate to project
cd excel-text2sql--main

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy config
cp .env.example .env

# Edit .env and add your Google API key
# GOOGLE_API_KEY=your-key-here

# Run the app
streamlit run app/streamlit_app.py
```

## 📝 Example Questions

Once you upload an Excel file, you can ask questions like:

- "What is the total sales?"
- "Who has the highest salary?"
- "Show top 10 customers by revenue"
- "What is the average age by department?"
- "Count employees by country"
- "Find all records where age > 30"

## 📁 Project Structure

```
excel-text2sql--main/
├── app/
│   ├── config.py           # Configuration settings
│   ├── llm_provider.py     # LLM wrapper (Gemini/OpenAI)
│   ├── text2sql.py         # Core Text2SQL pipeline
│   └── streamlit_app.py    # Streamlit UI
├── database/               # SQLite database (auto-created)
├── .env                    # Environment variables
├── .env.example            # Example config
├── requirements.txt        # Dependencies
└── README.md
```

## 🔑 Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `LLM_PROVIDER` | LLM provider | `gemini` |
| `LLM_MODEL` | Model name | `gemini-2.0-flash` |
| `GOOGLE_API_KEY` | Google Gemini API key | - |
| `DB_PATH` | SQLite database path | `./database/text2sql.db` |
| `TABLE_NAME` | Default table name | `excel_data` |

## 🆚 Text2SQL vs RAG

| Feature | Text2SQL | RAG |
|---------|----------|-----|
| **Data Type** | Structured (tables) | Unstructured (text) |
| **Query Method** | SQL queries | Vector similarity |
| **Best For** | Analytics, aggregations | Document search |
| **Accuracy** | Exact results | Approximate matches |
| **File Types** | Excel, CSV, databases | PDF, Word, text |

## 📦 Dependencies

- `langchain` - LLM framework
- `langchain-google-genai` - Gemini integration
- `langchain-openai` - OpenAI integration
- `pandas` - Data manipulation
- `openpyxl` - Excel reading
- `streamlit` - Web UI

## 🔧 Getting API Keys

- **Google Gemini**: Get free API key at [Google AI Studio](https://aistudio.google.com/apikey)
- **OpenAI**: Get API key at [OpenAI Platform](https://platform.openai.com/api-keys)