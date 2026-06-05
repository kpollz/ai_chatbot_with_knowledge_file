"""
Issue Management — Browse (with pagination), Create (Excel-style form with preview),
Edit / Delete
"""

import sys
from pathlib import Path

# Add parent dir so we can import api_client, logger, etc.
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import pandas as pd
from api_client import (
    get_issues_sync, get_issues_count_sync, get_issue_sync,
    create_issue_sync, update_issue_sync, delete_issue_sync,
    import_issue_sync,
    get_teams_sync, get_lines_sync, get_machines_sync,
    find_team_by_name_sync, find_line_by_name_sync, find_machine_by_details_sync,
)

st.set_page_config(page_title="Issue Management", page_icon="📋", layout="wide")
st.title("📋 Quản lý vấn đề máy móc")
st.markdown("Duyệt, tạo mới, chỉnh sửa và xóa các vấn đề máy móc trong hệ thống.")


# ---- Load reference data ----

@st.cache_data(ttl=60)
def load_teams():
    return get_teams_sync()

@st.cache_data(ttl=60)
def load_lines():
    return get_lines_sync()

@st.cache_data(ttl=60)
def load_machines():
    return get_machines_sync()

@st.cache_data(ttl=30)
def load_issues_page(skip: int, limit: int):
    return get_issues_sync(skip=skip, limit=limit)

@st.cache_data(ttl=30)
def load_issues_count():
    return get_issues_count_sync()

try:
    teams = load_teams()
    lines = load_lines()
    machines = load_machines()
except Exception as e:
    st.error(f"Không thể kết nối đến Issue API: {e}")
    st.stop()


# Build lookup maps
machine_options = {f"{m['MachineName']} (ID: {m['MachineID']})": m["MachineID"] for m in machines}
machine_id_to_name = {m["MachineID"]: m["MachineName"] for m in machines}
line_id_to_number = {l["LineID"]: l["LineName"] for l in lines}
team_id_to_name = {t["TeamID"]: t["TeamName"] for t in teams}


# ---- Helper functions ----

def check_team_line_machine(team_name: str, line_name: str, machine_name: str,
                            location: str = None, serial: str = None) -> dict:
    """
    Check if Team, Line, Machine exist. Returns status dict.
    """
    result = {
        "team": {"exists": False, "name": team_name, "id": None, "message": ""},
        "line": {"exists": False, "name": line_name, "id": None, "message": ""},
        "machine": {"exists": False, "name": machine_name, "id": None, "message": ""},
        "ok": False,
    }

    # Check Team
    if not team_name.strip():
        result["team"]["message"] = "⚠️ Chưa nhập Team"
        return result

    try:
        team = find_team_by_name_sync(team_name)
        result["team"]["exists"] = True
        result["team"]["id"] = team["TeamID"]
        result["team"]["message"] = f"✅ Team '{team_name}' đã tồn tại (ID: {team['TeamID']})"
    except Exception:
        result["team"]["message"] = f"🆕 Team '{team_name}' sẽ được tạo mới"

    # Check Line
    if not line_name.strip():
        result["line"]["message"] = "⚠️ Chưa nhập Line"
        return result

    if result["team"]["exists"]:
        try:
            line = find_line_by_name_sync(line_name, result["team"]["id"])
            result["line"]["exists"] = True
            result["line"]["id"] = line["LineID"]
            result["line"]["message"] = f"✅ Line '{line_name}' đã tồn tại (ID: {line['LineID']})"
        except Exception:
            result["line"]["message"] = f"🆕 Line '{line_name}' sẽ được tạo mới"
    else:
        result["line"]["message"] = f"🆕 Line '{line_name}' sẽ được tạo mới (cùng Team mới)"

    # Check Machine
    if not machine_name.strip():
        result["machine"]["message"] = "⚠️ Chưa nhập Machine"
        return result

    if result["line"]["exists"]:
        try:
            machines_found = find_machine_by_details_sync(
                machine_name, result["line"]["id"],
                location=location, serial=serial
            )
            if machines_found:
                m = machines_found[0]
                result["machine"]["exists"] = True
                result["machine"]["id"] = m["MachineID"]
                result["machine"]["message"] = f"✅ Machine '{machine_name}' đã tồn tại (ID: {m['MachineID']})"
            else:
                result["machine"]["message"] = f"🆕 Machine '{machine_name}' sẽ được tạo mới"
        except Exception:
            result["machine"]["message"] = f"🆕 Machine '{machine_name}' sẽ được tạo mới"
    else:
        result["machine"]["message"] = f"🆕 Machine '{machine_name}' sẽ được tạo mới (cùng Line mới)"

    result["ok"] = True
    return result


# ---- Tabs ----

tab_browse, tab_create, tab_edit = st.tabs(["📋 Duyệt (Browse)", "➕ Tạo mới (Create)", "✏️ Chỉnh sửa / Xóa"])


# ---- Session state init for pagination ----
if "issues_page_num" not in st.session_state:
    st.session_state.issues_page_num = 1


# ========== TAB: Browse with Pagination ==========
with tab_browse:
    col_controls, col_refresh = st.columns([6, 1])

    with col_controls:
        page_size_options = [10, 25, 50, 100]
        col1, col2, col3 = st.columns([1, 1, 4])
        with col1:
            page_size = st.selectbox("Số dòng/trang", options=page_size_options, index=1)

        try:
            total_issues = load_issues_count()
        except Exception as e:
            st.error(f"Không thể lấy tổng số issues: {e}")
            total_issues = 0

        total_pages = max(1, (total_issues + page_size - 1) // page_size)

        # Clamp page number to valid range when page size changes
        if st.session_state.issues_page_num > total_pages:
            st.session_state.issues_page_num = total_pages
        if st.session_state.issues_page_num < 1:
            st.session_state.issues_page_num = 1

        with col2:
            page_num = st.number_input(
                "Trang", min_value=1, max_value=total_pages,
                value=st.session_state.issues_page_num, step=1,
            )

        # Sync widget value back to session state
        st.session_state.issues_page_num = page_num

        with col3:
            st.markdown(f"""
                <div style="padding-top: 32px;">
                    Tổng: <b>{total_issues}</b> issues | Trang <b>{page_num}</b> / <b>{total_pages}</b>
                </div>
            """, unsafe_allow_html=True)

    with col_refresh:
        if st.button("🔄 Làm mới", use_container_width=True):
            st.cache_data.clear()
            st.session_state.issues_page_num = 1
            st.rerun()

    skip = (page_num - 1) * page_size

    try:
        issues = load_issues_page(skip=skip, limit=page_size)
    except Exception as e:
        st.error(f"Không thể tải danh sách issues: {e}")
        issues = []

    if issues:
        df = pd.DataFrame(issues)

        # Enrich with related names
        df["MachineName"] = df["MachineID"].map(machine_id_to_name)
        # Map LineID from machines, then to line number
        machine_id_to_line_id = {m["MachineID"]: m["LineID"] for m in machines}
        df["LineID"] = df["MachineID"].map(machine_id_to_line_id)
        df["LineName"] = df["LineID"].map(lambda x: line_id_to_number.get(x, "N/A"))

        # Reorder and select columns for display
        display_cols = [
            "IssueID", "LineName", "MachineName", "Date", "start_time", "stop_time", "total_time",
            "Week", "Year", "symptom", "cause", "solution", "PIC", "user_input",
        ]
        available_cols = [c for c in display_cols if c in df.columns]
        df_display = df[available_cols].copy()

        # Rename for display
        df_display = df_display.rename(columns={
            "LineName": "Line",
            "MachineName": "Máy",
            "symptom": "Hiện tượng",
            "cause": "Nguyên nhân",
            "solution": "Khắc phục",
            "start_time": "Bắt đầu",
            "stop_time": "Kết thúc",
            "total_time": "Tổng TG",
            "user_input": "Ghi chú",
        })

        st.dataframe(df_display, use_container_width=True, hide_index=True)
    else:
        st.info("Không có issue nào.")

    # Pagination buttons using callbacks to avoid direct session_state assignment to widget keys
    def _go_prev():
        st.session_state.issues_page_num = max(1, st.session_state.issues_page_num - 1)

    def _go_next():
        st.session_state.issues_page_num = min(total_pages, st.session_state.issues_page_num + 1)

    col_prev, col_spacer, col_next = st.columns([1, 3, 1])
    with col_prev:
        st.button("◀ Trang trước", disabled=(page_num <= 1), use_container_width=True, on_click=_go_prev)
    with col_next:
        st.button("Trang sau ▶", disabled=(page_num >= total_pages), use_container_width=True, on_click=_go_next)


# ========== TAB: Create (Excel-style form) ==========
with tab_create:
    st.subheader("➕ Tạo Issue mới")
    st.markdown("Nhập thông tin theo định dạng Excel. Hệ thống sẽ tự động kiểm tra và tạo Team/Line/Machine nếu chưa có.")

    with st.container(border=True):
        st.markdown("**Thông tin định danh máy**")
        col_t1, col_t2, col_t3, col_t4, col_t5 = st.columns(5)
        with col_t1:
            # Team autocomplete from existing teams
            team_names = [t["TeamName"] for t in teams] if teams else []
            team_name = st.text_input("Team *", placeholder="VD: Team A", key="create_team_name")
            if team_names and team_name:
                matched = [n for n in team_names if team_name.lower() in n.lower()]
                if matched:
                    st.caption(f"💡 Gợi ý: {', '.join(matched[:3])}")
        with col_t2:
            line_name = st.text_input("Line *", placeholder="VD: 2", key="create_line_name")
        with col_t3:
            machine_name = st.text_input("Machine *", placeholder="VD: CNC-01", key="create_machine_name")
        with col_t4:
            location = st.text_input("Location", placeholder="VD: A2", key="create_location")
        with col_t5:
            serial = st.text_input("Serial", placeholder="VD: SN12345", key="create_serial")

    with st.container(border=True):
        st.markdown("**Thời gian & Thông số**")
        col_d1, col_d2, col_d3, col_d4 = st.columns(4)
        with col_d1:
            date_val = st.text_input("Date", placeholder="2026-04-07", key="create_date")
        with col_d2:
            start_time = st.text_input("Start Time", placeholder="08:00", key="create_start_time")
        with col_d3:
            stop_time = st.text_input("Stop Time", placeholder="08:30", key="create_stop_time")
        with col_d4:
            total_time = st.text_input("Total Time", placeholder="30", key="create_total_time")

        col_w1, col_w2, col_w3 = st.columns(3)
        with col_w1:
            week = st.number_input("Week", min_value=1, max_value=53, value=None, key="create_week")
        with col_w2:
            year = st.number_input("Year", min_value=2020, max_value=2030, value=None, key="create_year")
        with col_w3:
            pic = st.text_input("PIC", placeholder="Người phụ trách", key="create_pic")

    with st.container(border=True):
        st.markdown("**Nội dung vấn đề**")
        symptom = st.text_area("Hiện tượng (Symptom) *", placeholder="Mô tả hiện tượng lỗi...", key="create_symptom")
        cause = st.text_area("Nguyên nhân (Cause) *", placeholder="Nguyên nhân gốc rễ...", key="create_cause")
        solution = st.text_area("Khắc phục (Solution) *", placeholder="Cách khắc phục...", key="create_solution")

    user_input_val = st.text_input("User Input / Ghi chú thêm", placeholder="Thông tin bổ sung...", key="create_user_input")

    # ---- Preview / Check section ----
    st.divider()

    col_check, col_create = st.columns([1, 1])

    preview_result = None
    with col_check:
        if st.button("🔍 Kiểm tra & Xem trước", type="secondary", use_container_width=True):
            if not team_name.strip() or not line_name.strip() or not machine_name.strip() or not symptom.strip() or not cause.strip() or not solution.strip():
                st.warning("Vui lòng nhập đầy đủ các trường bắt buộc: Team, Line, Machine, Hiện tượng, Nguyên nhân, Khắc phục.")
            else:
                preview_result = check_team_line_machine(
                    team_name, line_name, machine_name,
                    location=location or None, serial=serial or None
                )
                st.session_state.create_preview = preview_result

    # Show preview if available
    if "create_preview" in st.session_state:
        preview = st.session_state.create_preview
        st.markdown("**📋 Kết quả kiểm tra:**")
        pcol1, pcol2, pcol3 = st.columns(3)
        with pcol1:
            st.info(preview["team"]["message"])
        with pcol2:
            st.info(preview["line"]["message"])
        with pcol3:
            st.info(preview["machine"]["message"])

        if preview["ok"]:
            st.success("✅ Có thể tạo Issue. Nhấn nút **Tạo Issue** bên dưới để xác nhận.")
        else:
            st.error("❌ Vui lòng kiểm tra lại thông tin trước khi tạo.")

    with col_create:
        if st.button("➕ Tạo Issue", type="primary", use_container_width=True):
            if not team_name.strip() or not line_name.strip() or not machine_name.strip() or not symptom.strip() or not cause.strip() or not solution.strip():
                st.warning("Vui lòng nhập đầy đủ các trường bắt buộc: Team, Line, Machine, Hiện tượng, Nguyên nhân, Khắc phục.")
            else:
                try:
                    data = {
                        "TeamName": team_name.strip(),
                        "LineName": line_name.strip(),
                        "MachineName": machine_name.strip(),
                        "Location": location.strip() if location else None,
                        "Serial": serial.strip() if serial else None,
                        "Date": date_val.strip() if date_val else None,
                        "start_time": start_time.strip() if start_time else None,
                        "stop_time": stop_time.strip() if stop_time else None,
                        "total_time": total_time.strip() if total_time else None,
                        "Week": week,
                        "Year": year,
                        "symptom": symptom.strip() if symptom else None,
                        "cause": cause.strip() if cause else None,
                        "solution": solution.strip() if solution else None,
                        "PIC": pic.strip() if pic else None,
                        "user_input": user_input_val.strip() if user_input_val else None,
                    }
                    result = import_issue_sync(data)

                    messages = []
                    if result.get("created_team"):
                        messages.append(f"🆕 Team '{team_name}' đã được tạo.")
                    if result.get("created_line"):
                        messages.append(f"🆕 Line '{line_name}' đã được tạo.")
                    if result.get("created_machine"):
                        messages.append(f"🆕 Machine '{machine_name}' đã được tạo.")
                    if result.get("is_duplicate"):
                        messages.append(f"⚠️ Issue trùng lặp (cùng máy + hiện tượng) — trả về Issue ID: {result['IssueID']}")
                    else:
                        messages.append(f"✅ Issue đã được tạo thành công! ID: {result['IssueID']}")

                    for msg in messages:
                        st.success(msg)

                    # Clear caches
                    st.cache_data.clear()
                    if "create_preview" in st.session_state:
                        del st.session_state.create_preview

                except Exception as e:
                    st.error(f"❌ Tạo issue thất bại: {e}")


# ========== TAB: Edit / Delete ==========
with tab_edit:
    issue_id = st.number_input("Nhập Issue ID cần chỉnh sửa", min_value=1, step=1, value=None, key="edit_issue_id")

    if issue_id:
        try:
            issue = get_issue_sync(int(issue_id))
        except Exception:
            st.error(f"Không tìm thấy Issue {issue_id}.")
            issue = None

        if issue:
            st.markdown("---")

            with st.form("edit_issue_form"):
                st.subheader(f"✏️ Chỉnh sửa Issue #{issue_id}")

                # Machine selection — find current
                current_key = next(
                    (k for k, v in machine_options.items() if v == issue["MachineID"]),
                    list(machine_options.keys())[0] if machine_options else None,
                )
                machine_keys = list(machine_options.keys())
                selected_machine = st.selectbox(
                    "Machine",
                    options=machine_keys,
                    index=machine_keys.index(current_key) if current_key in machine_keys else 0,
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

                symptom = st.text_area("Hiện tượng", value=issue.get("symptom") or "")
                cause = st.text_area("Nguyên nhân", value=issue.get("cause") or "")
                solution = st.text_area("Khắc phục", value=issue.get("solution") or "")
                user_input_val = st.text_input("User Input", value=issue.get("user_input") or "")

                col_save, col_delete = st.columns(2)
                with col_save:
                    save_btn = st.form_submit_button("💾 Lưu thay đổi", type="primary")
                with col_delete:
                    delete_btn = st.form_submit_button("🗑️ Xóa Issue")

                if save_btn:
                    update_data = {
                        "MachineID": machine_id,
                        "Date": date or None,
                        "start_time": start_time or None,
                        "total_time": total_time or None,
                        "Week": week,
                        "Year": year,
                        "symptom": symptom or None,
                        "cause": cause or None,
                        "solution": solution or None,
                        "PIC": pic or None,
                        "user_input": user_input_val or None,
                    }
                    try:
                        update_issue_sync(int(issue_id), update_data)
                        st.success(f"✅ Issue {issue_id} đã được cập nhật!")
                        st.cache_data.clear()
                    except Exception as e:
                        st.error(f"❌ Cập nhật thất bại: {e}")

                if delete_btn:
                    try:
                        delete_issue_sync(int(issue_id))
                        st.success(f"✅ Issue {issue_id} đã được xóa!")
                        st.cache_data.clear()
                    except Exception as e:
                        st.error(f"❌ Xóa thất bại: {e}")
