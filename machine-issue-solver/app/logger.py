"""Logger utility for Machine Issue Solver"""

import logging
import time
from functools import wraps
from contextlib import contextmanager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("issue-solver")

def log_time(name: str):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.time()
            logger.info(f"Starting: {name}")
            try:
                result = func(*args, **kwargs)
                elapsed = time.time() - start
                logger.info(f"Completed: {name} in {elapsed:.2f}s")
                return result
            except Exception as e:
                elapsed = time.time() - start
                logger.error(f"Failed: {name} after {elapsed:.2f}s - {e}")
                raise
        return wrapper
    return decorator

@contextmanager
def Timer(name: str):
    start = time.time()
    logger.info(f"Starting: {name}")
    try:
        yield
    finally:
        elapsed = time.time() - start
        logger.info(f"Completed: {name} in {elapsed:.2f}s")