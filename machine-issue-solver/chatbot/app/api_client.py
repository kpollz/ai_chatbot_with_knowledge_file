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
