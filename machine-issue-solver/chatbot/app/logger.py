"""Logger utility for Chatbot"""

import logging
import time
from contextlib import contextmanager

import os

_log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, _log_level, logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("chatbot")
logger.setLevel(getattr(logging, _log_level, logging.INFO))


@contextmanager
def Timer(name: str):
    start = time.time()
    logger.info(f"Starting: {name}")
    try:
        yield
    finally:
        elapsed = time.time() - start
        logger.info(f"Completed: {name} in {elapsed:.2f}s")
