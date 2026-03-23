"""
Streamlit UI for Machine Issue Solver — Chat Page with Streaming
"""

from datetime import datetime
import streamlit as st
from graph import solve_issue_stream, StreamResult
from history import check_context_limit
from conversation_store import create_session_id, save_conversation
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

# Sidebar
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
    st.header("🔑 API Key")

    def _save_api_key():
        st.session_state.api_key = st.session_state._api_key_widget

    api_key = st.text_input(
        "Enter your LLM API Key",
        type="password",
        key="_api_key_widget",
        value=st.session_state.get("api_key", ""),
        placeholder="Paste your API key here...",
        help="Get your API key at https://mycompany.com/api/keys",
        on_change=_save_api_key,
    )
    # Also sync on first load (in case restored from session state)
    if api_key:
        st.session_state.api_key = api_key

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


# ---- Session initialization ----
if "session_id" not in st.session_state:
    st.session_state.session_id = create_session_id()
if "messages" not in st.session_state:
    st.session_state.messages = []

session_id = st.session_state.session_id


# ---- Display chat history with feedback ----
for i, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        # Feedback widget for assistant messages
        if message["role"] == "assistant":
            st.feedback("thumbs", key=f"fb_{session_id}_{i}")

# Sync feedback from widgets → message dicts → JSON file
feedback_changed = False
for i, message in enumerate(st.session_state.messages):
    if message["role"] == "assistant":
        fb_val = st.session_state.get(f"fb_{session_id}_{i}")
        if fb_val is not None:
            new_fb = "like" if fb_val == 1 else "dislike"
            if message.get("feedback") != new_fb:
                message["feedback"] = new_fb
                feedback_changed = True
if feedback_changed:
    save_conversation(session_id, st.session_state.messages)


# ---- Context limit check ----
context_status, context_tokens = check_context_limit(st.session_state.messages)
if context_status == "exceeded":
    st.error("⚠️ **Session context limit reached.** Please clear the chat and start a new session.")

# ---- API key check ----
chat_disabled = context_status == "exceeded" or not api_key
if not api_key:
    st.info("🔑 Please enter your LLM API Key in the sidebar to start chatting.")


# ---- Chat input ----
if prompt := st.chat_input("Ask about a machine issue...", disabled=chat_disabled):
    # Add user message
    user_msg = {"role": "user", "content": prompt, "timestamp": datetime.now().isoformat()}
    st.session_state.messages.append(user_msg)
    with st.chat_message("user"):
        st.markdown(prompt)

    if context_status == "warning":
        st.warning(f"⚠️ Context ~{context_tokens:,} tokens. Consider starting a new session soon.")

    # Process with ReAct agent (streaming via LangChain standard)
    with st.chat_message("assistant"):
        try:
            history = st.session_state.messages[:-1]
            stream_result = StreamResult()

            # st.spinner shows indicator while waiting for first token / tool execution
            with st.spinner("Thinking..."):
                response = st.write_stream(
                    solve_issue_stream(prompt, history=history, api_key=api_key,
                                       result=stream_result)
                )

            # Check for errors from the stream
            if stream_result.error:
                st.error(f"❌ {stream_result.error}")
                response = response or f"Error: {stream_result.error}"

            # Show issues if found (after streaming completes)
            if stream_result.issues:
                with st.expander(f"📚 Found {len(stream_result.issues)} related issues",
                                 expanded=False):
                    for j, issue in enumerate(stream_result.issues, 1):
                        st.markdown(f"**Issue {j}:** ({issue.get('Date', 'N/A')})")
                        st.markdown(f"- **Hiện tượng:** {issue.get('hien_tuong', 'N/A')}")
                        st.markdown(f"- **Nguyên nhân:** {issue.get('nguyen_nhan', 'N/A')}")
                        st.markdown(f"- **Khắc phục:** {issue.get('khac_phuc', 'N/A')}")
                        st.markdown(f"- **PIC:** {issue.get('PIC', 'N/A')}")
                        st.divider()

        except Exception as e:
            response = f"❌ An error occurred: {str(e)}"
            st.error(response)
            logger.error(f"Streaming error: {e}")

        response = response or "No response generated."

        # Append assistant message
        assistant_msg = {
            "role": "assistant",
            "content": response,
            "timestamp": datetime.now().isoformat(),
            "feedback": None,
        }
        st.session_state.messages.append(assistant_msg)

        # Feedback widget for new message
        fb_idx = len(st.session_state.messages) - 1
        st.feedback("thumbs", key=f"fb_{session_id}_{fb_idx}")

        # Auto-save conversation
        save_conversation(session_id, st.session_state.messages)


# ---- Clear chat ----
if st.sidebar.button("🗑️ Clear Chat (New Session)"):
    st.session_state.messages = []
    st.session_state.session_id = create_session_id()
    st.rerun()
