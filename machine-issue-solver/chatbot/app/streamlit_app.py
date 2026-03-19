"""
Streamlit UI for Machine Issue Solver (ReAct Agent with tool calling)
"""

import asyncio
import streamlit as st
from graph import solve_issue
from history import check_context_limit
from logger import logger


def run_async(coro):
    """Bridge async coroutine into Streamlit's sync context."""
    return asyncio.run(coro)


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
    1. Ask any question about machine issues
    2. The chatbot will search the database when needed
    3. You can also ask general questions

    **Example queries:**
    - "Toi can giai phap cho may CNC-01 tren Line 2"
    - "Machine Robot Arm o Line 1 bi loi gi?"
    - "Ban la ai?"
    - "Co nhung may nao trong he thong?"

    **Follow-up:** You don't need to repeat the line number — the chatbot remembers context.
    """)

    st.divider()
    st.header("⚙️ System Info")
    st.info("Using Company LLM (Gauss)")
    st.success("Connected to Issue API")

    # Context usage indicator
    if "messages" in st.session_state and st.session_state.messages:
        status, tokens = check_context_limit(st.session_state.messages)
        pct = min(tokens / 128000 * 100, 100)
        if status == "exceeded":
            st.error(f"Context: ~{tokens:,} tokens ({pct:.0f}%) — LIMIT REACHED")
        elif status == "warning":
            st.warning(f"Context: ~{tokens:,} tokens ({pct:.0f}%) — approaching limit")
        else:
            st.caption(f"Context: ~{tokens:,} tokens ({pct:.0f}%)")

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Check context limit before accepting input
context_status, context_tokens = check_context_limit(st.session_state.messages)

if context_status == "exceeded":
    st.error(
        "⚠️ **Session context limit reached.** "
        "Please clear the chat and start a new session to continue."
    )

# Chat input
if prompt := st.chat_input("Ask about a machine issue...", disabled=(context_status == "exceeded")):
    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Show warning if approaching limit
    if context_status == "warning":
        st.warning(
            f"⚠️ Context window is ~{context_tokens:,} tokens. "
            "Consider starting a new session soon."
        )

    # Process with ReAct agent (async)
    with st.chat_message("assistant"):
        with st.spinner("Processing..."):
            try:
                # Pass conversation history (exclude current message)
                history = st.session_state.messages[:-1]
                result = run_async(solve_issue(prompt, history=history))

                if result.get("error") and not result.get("response"):
                    response = f"❌ **Error**\n\n{result['error']}"
                    st.markdown(response)
                else:
                    # Show issues if any were found during tool calls
                    issues = result.get("issues", [])
                    if issues:
                        with st.expander(f"📚 Found {len(issues)} related issues", expanded=False):
                            for i, issue in enumerate(issues, 1):
                                st.markdown(f"**Issue {i}:** ({issue.get('Date', 'N/A')})")
                                st.markdown(f"- **Hiện tượng:** {issue.get('hien_tuong', 'N/A')}")
                                st.markdown(f"- **Nguyên nhân:** {issue.get('nguyen_nhan', 'N/A')}")
                                st.markdown(f"- **Khắc phục:** {issue.get('khac_phuc', 'N/A')}")
                                st.markdown(f"- **PIC:** {issue.get('PIC', 'N/A')}")
                                st.divider()

                    # Show agent response
                    response = result.get("response", "No response generated.")
                    st.markdown(response)

                st.session_state.messages.append({"role": "assistant", "content": response})

            except Exception as e:
                error_msg = f"❌ An error occurred: {str(e)}"
                st.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})

# Clear chat button
if st.sidebar.button("🗑️ Clear Chat (New Session)"):
    st.session_state.messages = []
    st.rerun()
