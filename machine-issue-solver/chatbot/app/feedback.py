"""
Feedback System — Rating + Dialog Forms + Langfuse Score Submission

Rating scale: 1-10
  - 1-6:  Form with Opinion, Best Answer (required), Harmful/Risk
  - 7-8:  Form with Opinion, Best Answer (optional)
  - 9-10: Form with Opinion, Best Answer checkbox
"""

import json
import streamlit as st
from langfuse import get_client
from logger import logger


def submit_feedback_to_langfuse(trace_id: str, score: int, opinion: str = "",
                                 best_answer: str = "", is_harmful: bool = False,
                                 is_best: bool = False) -> bool:
    """Submit user feedback as a single Langfuse score on the trace."""
    if not trace_id:
        logger.warning("Cannot submit feedback: no trace_id")
        return False

    try:
        comment_data = {
            "opinion": opinion.strip() if opinion else "",
            "best_answer": best_answer.strip() if best_answer else "",
            "harmful_risk": is_harmful,
            "is_best_answer": is_best,
        }
        comment_str = json.dumps(comment_data, ensure_ascii=False)

        client = get_client()
        client.create_score(
            trace_id=trace_id,
            name="user-feedback",
            value=score,
            comment=comment_str,
        )
        logger.info(f"Feedback submitted: score={score}, trace_id={trace_id[:16]}...")
        return True
    except Exception as e:
        logger.error(f"Failed to submit feedback to Langfuse: {e}")
        return False


def _get_form_fields(score: int) -> dict:
    """Determine which fields to show based on score."""
    return {
        "show_harmful": score <= 6,
        "best_answer_required": score <= 6,
        "best_answer_is_checkbox": score >= 9,
    }


@st.dialog("📝 Feedback")
def _feedback_dialog(score: int, trace_id: str, msg_index: int):
    """Modal dialog for collecting detailed feedback."""
    fields = _get_form_fields(score)

    score_emoji = "😊" if score >= 9 else "🙂" if score >= 7 else "😐" if score >= 4 else "😞"
    st.markdown(f"### {score_emoji} Rating: **{score}/10**")
    st.divider()

    # Opinion (always shown)
    opinion = st.text_area(
        "💬 Ý kiến của bạn",
        placeholder="Nhập ý kiến của bạn về câu trả lời này...",
        key=f"fb_opinion_{msg_index}"
    )

    # Best Answer
    best_answer = ""
    is_best = False
    if fields["best_answer_is_checkbox"]:
        # Score 9-10: checkbox
        is_best = st.checkbox(
            "⭐ Bạn có nghĩ đây là câu trả lời tốt nhất?",
            key=f"fb_best_{msg_index}"
        )
    else:
        # Score 1-8: text input
        label = "✏️ Câu trả lời tốt nhất nên là gì?"
        if fields["best_answer_required"]:
            label += " *"
        best_answer = st.text_input(
            label,
            placeholder="Nhập câu trả lời mà bạn mong đợi..." if score <= 6 else "Nhập câu trả lời tốt hơn (nếu có)...",
            key=f"fb_best_{msg_index}"
        )

    # Harmful/Risk (only for 1-6)
    is_harmful = False
    if fields["show_harmful"]:
        is_harmful = st.checkbox(
            "⚠️ Bạn có nghĩ câu trả lời này harmful/risk không?",
            key=f"fb_harmful_{msg_index}"
        )

    # Validation
    can_submit = True
    if fields["best_answer_required"] and not best_answer.strip():
        can_submit = False
        st.caption("(*) Trường bắt buộc")

    if st.button("✅ Gửi Feedback", type="primary", disabled=not can_submit, use_container_width=True):
        success = submit_feedback_to_langfuse(
            trace_id=trace_id,
            score=score,
            opinion=opinion,
            best_answer=best_answer,
            is_harmful=is_harmful,
            is_best=is_best,
        )
        if success:
            st.session_state[f"fb_submitted_{msg_index}"] = True
            st.session_state[f"fb_score_{msg_index}"] = score
            st.success("Cảm ơn bạn đã đánh giá! 🎉")
        else:
            st.error("Không thể gửi feedback. Vui lòng thử lại.")
        st.rerun()


def render_feedback_widget(msg_index: int, trace_id: str = None):
    """Render the feedback rating widget below an assistant message."""
    already_submitted = st.session_state.get(f"fb_submitted_{msg_index}", False)
    submitted_score = st.session_state.get(f"fb_score_{msg_index}", None)

    if already_submitted:
        emoji = "😊" if submitted_score >= 9 else "🙂" if submitted_score >= 7 else "😐" if submitted_score >= 4 else "😞"
        st.markdown(f"{emoji} Đã đánh giá: **{submitted_score}/10**")
        return

    # Rating slider + submit button
    col1, col2 = st.columns([3, 1])
    with col1:
        score = st.select_slider(
            "⭐ Đánh giá",
            options=list(range(1, 11)),
            value=5,
            key=f"fb_rating_{msg_index}",
            label_visibility="collapsed",
        )
    with col2:
        if st.button("📝 Gửi", key=f"fb_btn_{msg_index}", type="primary"):
            st.session_state[f"fb_dialog_score_{msg_index}"] = score
            st.session_state[f"fb_dialog_open_{msg_index}"] = True

    score_labels = {
        1: "😞 Rất tệ", 2: "😞 Tệ", 3: "😞 Tệ",
        4: "😐 Dưới TB", 5: "😐 TB", 6: "😐 Trên TB",
        7: "🙂 Tốt", 8: "🙂 Rất tốt",
        9: "😊 Tuyệt vời", 10: "😊 Hoàn hảo"
    }
    st.caption(f"Đã chọn: {score}/10 — {score_labels.get(score, '')}")

    # Open dialog if button was clicked
    if st.session_state.get(f"fb_dialog_open_{msg_index}", False):
        st.session_state[f"fb_dialog_open_{msg_index}"] = False
        dialog_score = st.session_state.get(f"fb_dialog_score_{msg_index}", score)
        _feedback_dialog(
            score=dialog_score,
            trace_id=trace_id or "",
            msg_index=msg_index,
        )