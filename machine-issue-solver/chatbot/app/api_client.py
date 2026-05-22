"""
HTTP client for Issue API (Sub-project 2)

Replaces direct SQLite queries — all database access goes through the Issue API.
"""

from typing import List, Dict
import httpx

from config import ISSUE_API_URL
from logger import logger


# ---- Sync operations ----

def _sync_request(method: str, path: str, params: dict = None, json_data: dict = None):
    """Sync HTTP request helper."""
    url = f"{ISSUE_API_URL}{path}"
    try:
        with httpx.Client(timeout=30) as client:
            response = client.request(method, url, params=params, json=json_data)
            response.raise_for_status()
            if response.status_code == 204:
                return None
            return response.json()
    except httpx.ConnectError:
        raise ConnectionError(f"Cannot connect to Issue API at {ISSUE_API_URL}.")
    except httpx.HTTPStatusError as e:
        logger.error(f"Issue API error: {e.response.status_code} - {e.response.text}")
        raise


def get_issues_sync(skip: int = 0, limit: int = 500) -> List[Dict]:
    return _sync_request("GET", "/issues/", params={"skip": skip, "limit": limit})


def get_issues_count_sync() -> int:
    return _sync_request("GET", "/issues/count")


def get_issue_sync(issue_id: int) -> Dict:
    return _sync_request("GET", f"/issues/{issue_id}")


def create_issue_sync(data: Dict) -> Dict:
    return _sync_request("POST", "/issues/", json_data=data)


def update_issue_sync(issue_id: int, data: Dict) -> Dict:
    return _sync_request("PUT", f"/issues/{issue_id}", json_data=data)


def delete_issue_sync(issue_id: int) -> None:
    _sync_request("DELETE", f"/issues/{issue_id}")


def get_lines_sync() -> List[Dict]:
    return _sync_request("GET", "/lines/")


def get_teams_sync() -> List[Dict]:
    """List all teams."""
    return _sync_request("GET", "/teams/")


def find_team_by_name_sync(team_name: str) -> Dict:
    """Find a team by name. Raises HTTPError if not found."""
    return _sync_request("GET", "/teams/find/by-name", params={"team_name": team_name})


def create_team_sync(team_name: str) -> Dict:
    """Create a new team."""
    return _sync_request("POST", "/teams/", json_data={"TeamName": team_name})


def find_line_by_name_sync(line_name: str, team_id: int) -> Dict:
    """Find a line by number within a team. Raises HTTPError if not found."""
    return _sync_request("GET", "/lines/find/by-name", params={"line_name": line_name, "team_id": team_id})


def find_machine_by_details_sync(machine_name: str, line_id: int, location: str = None, serial: str = None) -> List[Dict]:
    """Find machines by name within a line."""
    params = {"machine_name": machine_name, "line_id": line_id}
    if location is not None:
        params["location"] = location
    if serial is not None:
        params["serial"] = serial
    return _sync_request("GET", "/machines/find/by-details", params=params)


def create_machine_sync(machine_name: str, line_id: int, location: str = None, serial: str = None) -> Dict:
    """Create a new machine under a line."""
    data = {"MachineName": machine_name, "LineID": line_id}
    if location is not None:
        data["Location"] = location
    if serial is not None:
        data["Serial"] = serial
    return _sync_request("POST", "/machines/", json_data=data)


def get_machines_sync() -> List[Dict]:
    return _sync_request("GET", "/machines/")


# ---- Sync tool functions (for streaming graph) ----

def search_issues_sync(machine_name: str, line_name: str,
                       location: str = None, serial: str = None) -> List[Dict]:
    """Sync version of search_issues for streaming flow."""
    params = {"machine_name": machine_name, "line_name": line_name}
    if location:
        params["location"] = location
    if serial:
        params["serial"] = serial
    issues = _sync_request("GET", "/issues/search", params=params)
    logger.info(f"Issue API returned {len(issues)} issues for '{machine_name}' on '{line_name}'"
                f"{f' location={location}' if location else ''}{f' serial={serial}' if serial else ''}")
    return issues


def import_issue_sync(data: Dict) -> Dict:
    """
    Import a full Excel row via POST /issues/import.
    Auto-creates Line, Team, Machine if not found.
    Returns dict with IssueID and what was created.
    """
    result = _sync_request("POST", "/issues/import", json_data=data)
    logger.info(f"Imported issue ID={result.get('IssueID')}, "
                f"created_line={result.get('created_line')}, "
                f"created_team={result.get('created_team')}, "
                f"created_machine={result.get('created_machine')}")
    return result
