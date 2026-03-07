"""
Streamlit UI for Machine Issue Solver
"""

import streamlit as st
from graph import solve_issue
from logger import logger

# Page config
st.set_page_config(
    page_title="Machine Issue Solver",
    page_icon="🔧",
    layout="wide"
)

# Title
st.title("🔧 Machine Issue Solver")
st.markdown("Ask about machine issues and get solutions based on your database.")

# Sidebar with instructions
with st.sidebar:
    st.header("📋 Instructions")
    st.markdown("""
    **How to use:**
    1. Enter your question about a machine issue
    2. Include the **machine name** and **line number**
    3. Click "Get Solution"
    
    **Example queries:**
    - "Tôi cần giải pháp cho máy CNC-01 trên Line 2"
    - "Machine Robot Arm ở Line 1 bị lỗi gì?"
    - "How to fix the issue on Packaging Machine at Line 3?"
    
    **Note:** The system will reject queries that don't include both machine name and line number.
    """)
    
    st.divider()
    st.header("⚙️ System Info")
    st.info("Using Company LLM (Gauss)")
    st.success("Connected to Issues Database")

# Main chat interface
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat input
if prompt := st.chat_input("Ask about a machine issue..."):
    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Process with LangGraph
    with st.chat_message("assistant"):
        with st.spinner("Processing..."):
            try:
                result = solve_issue(prompt)
                
                # Check if rejected
                if result.get("rejection_reason"):
                    response = f"⚠️ **Cannot Process Request**\n\n{result['rejection_reason']}"
                    st.markdown(response)
                elif result.get("error") and not result.get("solution"):
                    response = f"❌ **Error**\n\n{result['error']}"
                    st.markdown(response)
                else:
                    # Show extracted info
                    st.markdown(f"**Machine:** {result.get('machine_name', 'N/A')}")
                    st.markdown(f"**Line:** {result.get('line_number', 'N/A')}")
                    
                    # Show issues found
                    issues = result.get("issues", [])
                    if issues:
                        with st.expander(f"📚 Found {len(issues)} related issues", expanded=False):
                            for i, issue in enumerate(issues, 1):
                                st.markdown(f"**Issue {i}:**")
                                st.markdown(f"- **Hiện tượng:** {issue.get('Hien tuong', 'N/A')}")
                                st.markdown(f"- **Nguyên nhân:** {issue.get('Nguyen nhan', 'N/A')}")
                                st.markdown(f"- **Khắc phục:** {issue.get('Khac phuc', 'N/A')}")
                                st.divider()
                    
                    # Show solution
                    st.markdown("---")
                    st.markdown("### 💡 Solution")
                    solution = result.get("solution", "No solution generated.")
                    st.markdown(solution)
                    
                    response = f"**Machine:** {result.get('machine_name')}\n\n**Solution:**\n{solution}"
                
                st.session_state.messages.append({"role": "assistant", "content": response})
                
            except Exception as e:
                error_msg = f"❌ An error occurred: {str(e)}"
                st.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})

# Clear chat button
if st.sidebar.button("Clear Chat"):
    st.session_state.messages = []
    st.rerun()