"""Streamlit UI for Simple Text2SQL"""

import streamlit as st
from text2sql import text2sql

st.set_page_config(page_title="Simple Text2SQL", page_icon="🔍", layout="wide")

st.title("🔍 Simple Text2SQL")
st.markdown("Ask questions about your database in natural language.")

# Sidebar
with st.sidebar:
    st.header("📋 Instructions")
    st.markdown("""
    1. Database and schema are pre-configured
    2. Just type your question
    3. View the generated SQL and results
    
    **Example questions:**
    - "Show all employees"
    - "What is the total sales?"
    - "Find customers from Hanoi"
    """)
    if st.button("Clear Chat"):
        st.session_state.messages = []
        st.rerun()

# Chat
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("Ask a question..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    
    with st.chat_message("assistant"):
        with st.spinner("Generating SQL..."):
            try:
                result = text2sql(prompt)
                
                st.code(result["sql"], language="sql")
                st.caption(f"Found {result['row_count']} rows")
                
                if result["results"]:
                    st.dataframe(result["results"], use_container_width=True)
                else:
                    st.info("No results found.")
                
                response = f"```sql\n{result['sql']}\n```\n\n{result['row_count']} rows"
            except Exception as e:
                response = f"❌ Error: {str(e)}"
                st.error(response)
        
        st.session_state.messages.append({"role": "assistant", "content": response})