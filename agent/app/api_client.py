"""HTTP client for the Issue API (Sub-project 2).

The agent never touches the database directly — every read goes through the API.
Only what the ``search_issues`` tool needs lives here; the CRUD helpers went with
the UI pages that were their sole caller.
"""

from typing import List, Dict
import atexit
import httpx

from config import ISSUE_API_URL
from logger import logger


# Shared client with a connection pool — reused across requests so calls to the
# Issue API keep TCP connections alive instead of doing a fresh handshake each
# time. httpx.Client is thread-safe, and the tool runs in a worker thread since
# it is a sync function called from an async graph. Closed at exit.
_client = httpx.Client(
    timeout=30,
    limits=httpx.Limits(max_keepalive_connections=20, max_connections=100),
)
atexit.register(_client.close)


def _sync_request(method: str, path: str, params: dict = None, json_data: dict = None):
    """Sync HTTP request helper."""
    url = f"{ISSUE_API_URL}{path}"
    try:
        response = _client.request(method, url, params=params, json=json_data)
        response.raise_for_status()
        if response.status_code == 204:
            return None
        return response.json()
    except httpx.ConnectError:
        raise ConnectionError(f"Cannot connect to Issue API at {ISSUE_API_URL}.")
    except httpx.HTTPStatusError as e:
        logger.error(f"Issue API error: {e.response.status_code} - {e.response.text}")
        raise


def search_issues_sync(machine_name: str, line_name: str,
                       location: str = None, serial: str = None) -> List[Dict]:
    """Issues recorded for one machine on one line — backs the agent's tool."""
    params = {"machine_name": machine_name, "line_name": line_name}
    if location:
        params["location"] = location
    if serial:
        params["serial"] = serial
    issues = _sync_request("GET", "/issues/search", params=params)
    logger.info(f"Issue API returned {len(issues)} issues for '{machine_name}' on '{line_name}'"
                f"{f' location={location}' if location else ''}{f' serial={serial}' if serial else ''}")
    return issues
