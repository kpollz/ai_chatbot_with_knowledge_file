# 🔧 Machine Issue Solver

A LangGraph-based application that answers user questions about machine issues using your company's LLM and a SQLite database.

## 🎯 Overview

This system uses **LangGraph** to create a stateful workflow that:
1. **Extracts** machine name and line number from user queries
2. **Validates** that enough information is provided
3. **Queries** the SQLite database for related issues
4. **Generates** solutions using your company's LLM

## 🔄 Workflow

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   START     │────▶│ Extract Info│────▶│  Check Info │────▶│   END       │
│             │     │  (LLM)      │     │  (Route)    │     │ (Rejected)  │
└─────────────┘     └─────────────┘     └──────┬──────┘     └─────────────┘
                                               │ Has Info
                                               ▼
                                        ┌─────────────┐
                                        │   Query     │
                                        │  Database   │
                                        └──────┬──────┘
                                               │
                                               ▼
                                        ┌─────────────┐
                                        │  Generate   │
                                        │  Solution   │
                                        │   (LLM)     │
                                        └──────┬──────┘
                                               │
                                               ▼
                                        ┌─────────────┐
                                        │    END      │
                                        └─────────────┘
```

## 📋 Database Schema

The application expects a SQLite database with the following tables:

```sql
-- Lines table
CREATE TABLE Lines (
    LineID INTEGER PRIMARY KEY,
    LineName TEXT NOT NULL
);

-- Teams table
CREATE TABLE Teams (
    TeamID INTEGER PRIMARY KEY,
    LineID INTEGER REFERENCES Lines(LineID)
);

-- Machines table
CREATE TABLE Machines (
    MachineID INTEGER PRIMARY KEY,
    MachineName TEXT NOT NULL,
    TeamID INTEGER REFERENCES Teams(TeamID)
);

-- Issues table
CREATE TABLE Issues (
    IssueID INTEGER PRIMARY KEY,
    MachineID INTEGER REFERENCES Machines(MachineID),
    "Hien tuong" TEXT,    -- Symptom
    "Nguyen nhan" TEXT,   -- Cause
    "Khac phuc" TEXT      -- Solution
);
```

## 🚀 Quickstart

### 1. Clone and Setup

```bash
cd machine-issue-solver

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy config
cp .env.example .env
```

### 2. Configure Environment

Edit `.env` with your company LLM credentials:

```env
LLM_PROVIDER=company
LLM_MODEL=Gauss2.3
LLM_TEMPERATURE=0

COMPANY_LLM_API_KEY=your-api-key
COMPANY_LLM_MODEL_ID=your-model-id
COMPANY_LLM_MODEL_URL=https://mycompany.com/api/v1/run/session_id

DB_PATH=./database/issues.db
```

### 3. Prepare Database

Place your SQLite database file at `./database/issues.db`

### 4. Run the Application

```bash
streamlit run app/streamlit_app.py
```

## 💬 Usage Examples

**Valid queries (include both machine name and line number):**
- "Tôi cần giải pháp cho máy CNC-01 trên Line 2"
- "Machine Robot Arm ở Line 1 bị lỗi gì?"
- "How to fix issues on Packaging Machine at Line 3?"

**Invalid queries (will be rejected):**
- "Machine CNC-01 has issues" (missing line number)
- "What's wrong with Line 2?" (missing machine name)
- "Help me fix this" (missing both)

## 📁 Project Structure

```
machine-issue-solver/
├── app/
│   ├── config.py              # Configuration settings
│   ├── company_chat_model.py  # Company LLM wrapper
│   ├── graph.py               # LangGraph workflow
│   ├── logger.py              # Logging utility
│   └── streamlit_app.py       # Streamlit UI
├── database/
│   └── issues.db              # SQLite database
├── .env.example               # Example configuration
├── requirements.txt           # Dependencies
└── README.md                  # This file
```

## 🔧 Available Company Models

| Model | Description |
|-------|-------------|
| Gauss2.3 | Standard model |
| Gauss2.3 Think | Thinking model |
| GaussO Flash | Fast model |
| GaussO Flash (S) | Fast model (S) |
| GaussO4 | O4 model |
| GaussO4 Thinking | O4 Thinking model |

## 🔑 Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `LLM_PROVIDER` | LLM provider | `company` |
| `LLM_MODEL` | Model name | `Gauss2.3` |
| `LLM_TEMPERATURE` | Sampling temperature | `0` |
| `COMPANY_LLM_API_KEY` | Company LLM API key | - |
| `COMPANY_LLM_MODEL_ID` | Custom model ID | - |
| `COMPANY_LLM_MODEL_URL` | Custom model URL | - |
| `DB_PATH` | SQLite database path | `./database/issues.db` |

## 📦 Dependencies

- `langgraph` - Workflow orchestration
- `langchain-core` - LangChain core components
- `langchain-community` - Community integrations
- `python-dotenv` - Environment management
- `requests` - HTTP requests
- `pydantic` - Data validation
- `streamlit` - Web UI