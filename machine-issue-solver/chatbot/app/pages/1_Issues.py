"""
Issue Management — Browse, Create, Edit, Delete issues via Issue API
"""

import sys
from pathlib import Path

# Add parent dir so we can import api_client, logger, etc.
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import pandas as pd
from api_client import (
    get_issues_sync, get_issue_sync, create_issue_sync,
    update_issue_sync, delete_issue_sync,
    get_lines_sync, get_machines_sync,
)

st.set_page_config(page_title="Issue Management", page_icon="📋", layout="wide")
st.title("📋 Issue Management")
st.markdown("Browse, create, edit, and delete machine issues.")


# ---- Load reference data ----

@st.cache_data(ttl=60)
def load_lines():
    return get_lines_sync()

@st.cache_data(ttl=60)
def load_machines():
    return get_machines_sync()

try:
    lines = load_lines()
    machines = load_machines()
except Exception as e:
    st.error(f"Cannot connect to Issue API: {e}")
    st.stop()


# Build lookup maps
machine_options = {f"{m['MachineName']} (ID: {m['MachineID']})": m["MachineID"] for m in machines}
machine_id_to_name = {m["MachineID"]: m["MachineName"] for m in machines}


# ---- Tabs ----

tab_browse, tab_create, tab_edit = st.tabs(["📋 Browse", "➕ Create", "✏️ Edit / Delete"])


# ========== TAB: Browse ==========
with tab_browse:
    # Refresh button
    if st.button("🔄 Refresh"):
        st.cache_data.clear()
        st.rerun()

    try:
        issues = get_issues_sync()
    except Exception as e:
        st.error(f"Failed to load issues: {e}")
        issues = []

    if issues:
        df = pd.DataFrame(issues)

        # Add machine name column
        df["MachineName"] = df["MachineID"].map(machine_id_to_name)

        # Reorder and select columns for display
        display_cols = [
            "IssueID", "MachineName", "Date", "start_time", "total_time",
            "hien_tuong", "nguyen_nhan", "khac_phuc", "PIC",
        ]
        available_cols = [c for c in display_cols if c in df.columns]
        df_display = df[available_cols].copy()

        # Rename for display
        df_display = df_display.rename(columns={
            "MachineName": "Machine",
            "hien_tuong": "Hiện tượng",
            "nguyen_nhan": "Nguyên nhân",
            "khac_phuc": "Khắc phục",
            "start_time": "Start Time",
            "total_time": "Total Time",
        })

        st.dataframe(df_display, use_container_width=True, hide_index=True)
        st.caption(f"Total: {len(issues)} issues")
    else:
        st.info("No issues found.")


# ========== TAB: Create ==========
with tab_create:
    with st.form("create_issue_form", clear_on_submit=True):
        st.subheader("Create New Issue")

        selected_machine = st.selectbox(
            "Machine *", options=list(machine_options.keys()), key="create_machine"
        )
        machine_id = machine_options.get(selected_machine)

        col1, col2 = st.columns(2)
        with col1:
            date = st.text_input("Date", placeholder="e.g., 2026-03-19")
            start_time = st.text_input("Start Time", placeholder="e.g., 08:00")
            total_time = st.text_input("Total Time", placeholder="e.g., 30")
        with col2:
            week = st.number_input("Week", min_value=1, max_value=53, value=None)
            year = st.number_input("Year", min_value=2020, max_value=2030, value=None)
            pic = st.text_input("PIC", placeholder="Person in charge")

        hien_tuong = st.text_area("Hiện tượng (Symptom)")
        nguyen_nhan = st.text_area("Nguyên nhân (Cause)")
        khac_phuc = st.text_area("Khắc phục (Solution)")
        user_input_val = st.text_input("User Input", placeholder="Additional notes")

        submitted = st.form_submit_button("Create Issue", type="primary")
        if submitted:
            data = {
                "MachineID": machine_id,
                "Date": date or None,
                "start_time": start_time or None,
                "total_time": total_time or None,
                "Week": week,
                "Year": year,
                "hien_tuong": hien_tuong or None,
                "nguyen_nhan": nguyen_nhan or None,
                "khac_phuc": khac_phuc or None,
                "PIC": pic or None,
                "user_input": user_input_val or None,
            }
            try:
                result = create_issue_sync(data)
                st.success(f"Issue created! ID: {result['IssueID']}")
                st.cache_data.clear()
            except Exception as e:
                st.error(f"Failed to create issue: {e}")


# ========== TAB: Edit / Delete ==========
with tab_edit:
    issue_id = st.number_input("Enter Issue ID to edit", min_value=1, step=1, value=None)

    if issue_id:
        try:
            issue = get_issue_sync(int(issue_id))
        except Exception:
            st.error(f"Issue {issue_id} not found.")
            issue = None

        if issue:
            st.markdown("---")

            with st.form("edit_issue_form"):
                st.subheader(f"Edit Issue #{issue_id}")

                # Machine selection — find current
                current_key = next(
                    (k for k, v in machine_options.items() if v == issue["MachineID"]),
                    list(machine_options.keys())[0],
                )
                selected_machine = st.selectbox(
                    "Machine",
                    options=list(machine_options.keys()),
                    index=list(machine_options.keys()).index(current_key),
                )
                machine_id = machine_options[selected_machine]

                col1, col2 = st.columns(2)
                with col1:
                    date = st.text_input("Date", value=issue.get("Date") or "")
                    start_time = st.text_input("Start Time", value=issue.get("start_time") or "")
                    total_time = st.text_input("Total Time", value=issue.get("total_time") or "")
                with col2:
                    week = st.number_input("Week", min_value=1, max_value=53, value=issue.get("Week"))
                    year = st.number_input("Year", min_value=2020, max_value=2030, value=issue.get("Year"))
                    pic = st.text_input("PIC", value=issue.get("PIC") or "")

                hien_tuong = st.text_area("Hiện tượng", value=issue.get("hien_tuong") or "")
                nguyen_nhan = st.text_area("Nguyên nhân", value=issue.get("nguyen_nhan") or "")
                khac_phuc = st.text_area("Khắc phục", value=issue.get("khac_phuc") or "")
                user_input_val = st.text_input("User Input", value=issue.get("user_input") or "")

                col_save, col_delete = st.columns(2)
                with col_save:
                    save_btn = st.form_submit_button("💾 Save Changes", type="primary")
                with col_delete:
                    delete_btn = st.form_submit_button("🗑️ Delete Issue")

                if save_btn:
                    update_data = {
                        "MachineID": machine_id,
                        "Date": date or None,
                        "start_time": start_time or None,
                        "total_time": total_time or None,
                        "Week": week,
                        "Year": year,
                        "hien_tuong": hien_tuong or None,
                        "nguyen_nhan": nguyen_nhan or None,
                        "khac_phuc": khac_phuc or None,
                        "PIC": pic or None,
                        "user_input": user_input_val or None,
                    }
                    try:
                        update_issue_sync(int(issue_id), update_data)
                        st.success(f"Issue {issue_id} updated!")
                        st.cache_data.clear()
                    except Exception as e:
                        st.error(f"Failed to update: {e}")

                if delete_btn:
                    try:
                        delete_issue_sync(int(issue_id))
                        st.success(f"Issue {issue_id} deleted!")
                        st.cache_data.clear()
                    except Exception as e:
                        st.error(f"Failed to delete: {e}")
