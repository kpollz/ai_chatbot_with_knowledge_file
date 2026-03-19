"""
Async HTTP client for Issue API (Sub-project 2)

Replaces direct SQLite queries — all database access goes through the Issue API.
"""

from typing import List, Dict
import httpx

from config import ISSUE_API_URL
from logger import logger


async def search_issues(machine_name: str, line_name: str) -> List[Dict]:
    """
    Search issues by machine name and line name.
    Calls GET /issues/search on the Issue API.
    """
    url = f"{ISSUE_API_URL}/issues/search"
    params = {"machine_name": machine_name, "line_name": line_name}

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            issues = response.json()
            logger.info(
                f"Issue API returned {len(issues)} issues "
                f"for machine '{machine_name}' on line '{line_name}'"
            )
            return issues
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
