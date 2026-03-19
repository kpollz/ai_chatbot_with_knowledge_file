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
