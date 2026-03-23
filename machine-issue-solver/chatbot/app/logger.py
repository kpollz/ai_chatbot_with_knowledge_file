"""Logger utility for Chatbot"""

import logging
import time
from contextlib import contextmanager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("chatbot")


@contextmanager
def Timer(name: str):
    start = time.time()
    logger.info(f"Starting: {name}")
    try:
        yield
    finally:
        elapsed = time.time() - start
        logger.info(f"Completed: {name} in {elapsed:.2f}s")
