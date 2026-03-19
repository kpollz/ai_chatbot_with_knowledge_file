"""
Async HTTP client for Issue API (Sub-project 2)

Replaces direct SQLite queries — all database access goes through the Issue API.
"""

from typing import List, Dict
import httpx

from config import ISSUE_API_URL
from logger import logger


async def _get(path: str, params: dict = None) -> list:
    """Shared GET helper with error handling."""
    url = f"{ISSUE_API_URL}{path}"
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json()
    except httpx.ConnectError:
        logger.error(f"Cannot connect to Issue API at {ISSUE_API_URL}")
        raise ConnectionError(
            f"Cannot connect to Issue API at {ISSUE_API_URL}. "
            "Make sure the Issue API service is running."
        )
    except httpx.HTTPStatusError as e:
        logger.error(f"Issue API error: {e.response.status_code} - {e.response.text}")
        raise
    except Exception as e:
        logger.error(f"Issue API request failed: {e}")
        raise


async def search_issues(machine_name: str, line_name: str) -> List[Dict]:
    """Search issues by machine name and line name."""
    issues = await _get("/issues/search", {"machine_name": machine_name, "line_name": line_name})
    logger.info(f"Issue API returned {len(issues)} issues for machine '{machine_name}' on line '{line_name}'")
    return issues


async def list_machines() -> List[Dict]:
    """List all machines."""
    machines = await _get("/machines/")
    logger.info(f"Issue API returned {len(machines)} machines")
    return machines


async def list_lines() -> List[Dict]:
    """List all production lines."""
    lines = await _get("/lines/")
    logger.info(f"Issue API returned {len(lines)} lines")
    return lines


# ---- Sync operations (for Streamlit CRUD pages) ----

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


def get_machines_sync() -> List[Dict]:
    return _sync_request("GET", "/machines/")
