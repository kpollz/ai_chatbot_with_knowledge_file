"""
Feedback System — Default 10/10 with optional user correction

Logic:
- Every assistant response is auto-scored 10/10 by default (best assumption).
- Users can click "Sửa đánh giá" to lower the score if the answer was not satisfactory.
- Star mapping: ⭐=2, ⭐⭐=4, ⭐⭐⭐=6, ⭐⭐⭐⭐=8, ⭐⭐⭐⭐⭐=10

Dialog forms by score range:
  - 2-6:  Opinion + Best Answer (required) + Harmful/Risk
  - 8:    Opinion + Best Answer (optional)
  - 10:   Opinion + Best Answer checkbox
"""

import json
import streamlit as st
from langfuse import get_client
from logger import logger


# Star value (0-4) → score (2,4,6,8,10)
STAR_SCORE_MAP = {0: 2, 1: 4, 2: 6, 3: 8, 4: 10}
# Reverse map for initializing star widgets
SCORE_STAR_MAP = {2: 0, 4: 1, 6: 2, 8: 3, 10: 4}


def submit_feedback_to_langfuse(trace_id: str, score: int, opinion: str = "",
                                 best_answer: str = "", is_harmful: bool = False,
                                 is_best: bool = False) -> bool:
    """Submit user feedback as a Langfuse score on the trace."""
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


@st.dialog("📝 Chỉnh sửa đánh giá")
def _feedback_dialog(current_score: int, trace_id: str, msg_index: int):
    """Modal dialog for users to change the default 10/10 rating."""
    stars_key = f"fb_dialog_stars_{msg_index}"

    # Default to the current score's star count so the widget is pre-filled
    if stars_key not in st.session_state:
        st.session_state[stars_key] = SCORE_STAR_MAP.get(current_score, 4)

    st.markdown("#### Chọn số sao phù hợp")
    star_val = st.feedback("stars", key=stars_key)

    # Use selected star value if available; otherwise keep current score
    if star_val is not None:
        score = STAR_SCORE_MAP.get(star_val, current_score)
    else:
        score = current_score

    score_emoji = "😊" if score >= 9 else "🙂" if score >= 7 else "😐" if score >= 4 else "😞"
    st.markdown(f"### {score_emoji} Rating: **{score}/10**")
    st.divider()

    fields = _get_form_fields(score)

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
        is_best = st.checkbox(
            "⭐ Bạn có nghĩ đây là câu trả lời tốt nhất?",
            key=f"fb_best_{msg_index}"
        )
    else:
        label = "✏️ Câu trả lời tốt nhất nên là gì?"
        if fields["best_answer_required"]:
            label += " *"
        best_answer = st.text_input(
            label,
            placeholder="Nhập câu trả lời mà bạn mong đợi..." if score <= 6 else "Nhập câu trả lời tốt hơn (nếu có)...",
            key=f"fb_best_{msg_index}"
        )

    # Harmful/Risk (only for low scores)
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

    if st.button("✅ Cập nhật đánh giá", type="primary", disabled=not can_submit, use_container_width=True):
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
            st.session_state[f"fb_auto_submitted_{msg_index}"] = False
            st.success("Cảm ơn bạn đã đánh giá! 🎉")
            st.rerun()
        else:
            st.error("Không thể gửi feedback. Vui lòng thử lại.")


def render_feedback_widget(msg_index: int, trace_id: str = None):
    """Render feedback widget. Defaults to 10/10 and lets users lower the score."""
    submitted_key = f"fb_submitted_{msg_index}"
    score_key = f"fb_score_{msg_index}"
    auto_key = f"fb_auto_submitted_{msg_index}"

    # Auto-submit a default 10/10 score once per message
    if (
        not st.session_state.get(submitted_key)
        and trace_id
        and not st.session_state.get(auto_key)
    ):
        success = submit_feedback_to_langfuse(
            trace_id=trace_id,
            score=10,
            opinion="",
            best_answer="",
            is_harmful=False,
            is_best=True,
        )
        if success:
            st.session_state[auto_key] = True
            st.session_state[submitted_key] = True
            st.session_state[score_key] = 10

    submitted = st.session_state.get(submitted_key, False)
    score = st.session_state.get(score_key, 10)
    is_auto = st.session_state.get(auto_key, False)

    # Subtle divider
    st.markdown(
        '<div style="border-top: 1px solid rgba(128,128,128,0.2); margin-top: 0.5rem; padding-top: 0.4rem;"></div>',
        unsafe_allow_html=True,
    )

    if submitted and score is not None:
        emoji = "😊" if score >= 9 else "🙂" if score >= 7 else "😐" if score >= 4 else "😞"
        if is_auto and score == 10:
            label = f"{emoji} Mặc định: {score}/10"
        else:
            label = f"{emoji} Đã đánh giá: {score}/10"

        col_label, col_edit = st.columns([3, 1])
        with col_label:
            st.markdown(
                f'<span style="color: gray; font-size: 0.85em;">{label}</span>',
                unsafe_allow_html=True,
            )
        with col_edit:
            if st.button("✏️ Sửa", key=f"fb_edit_{msg_index}"):
                st.session_state[f"fb_dialog_open_{msg_index}"] = True
                st.session_state[f"fb_dialog_score_{msg_index}"] = score
                st.rerun()
    else:
        # Fallback if auto-submit failed or no trace_id — show manual widget
        st.markdown(
            '<p style="color: rgba(128,128,128,0.6); font-size: 0.8em; margin: 0.2rem 0 0.3rem 0;">'
            'Hãy để lại feedback của bạn</p>',
            unsafe_allow_html=True,
        )
        star_val = st.feedback(
            "stars",
            key=f"fb_stars_{msg_index}",
        )
        if star_val is not None:
            score = STAR_SCORE_MAP.get(star_val, 6)
            st.session_state[f"fb_dialog_open_{msg_index}"] = True
            st.session_state[f"fb_dialog_score_{msg_index}"] = score

    # Open dialog if requested
    if st.session_state.get(f"fb_dialog_open_{msg_index}", False):
        st.session_state[f"fb_dialog_open_{msg_index}"] = False
        dialog_score = st.session_state.get(f"fb_dialog_score_{msg_index}", 10)
        _feedback_dialog(
            current_score=dialog_score,
            trace_id=trace_id or "",
            msg_index=msg_index,
        )
