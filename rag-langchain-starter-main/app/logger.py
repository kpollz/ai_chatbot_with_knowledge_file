"""
Simple Logger Utility

Provides timing and logging for each step of the RAG pipeline.
"""

import logging
import time
from datetime import datetime
from typing import Optional
from functools import wraps


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger("rag")


def log_time(operation: str):
    """
    Decorator to log execution time of a function.
    
    Usage:
        @log_time("Load documents")
        def load_documents(file_path):
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.time()
            logger.info(f"[START] {operation}...")
            try:
                result = func(*args, **kwargs)
                elapsed = time.time() - start
                logger.info(f"[DONE] {operation} - {elapsed:.2f}s")
                return result
            except Exception as e:
                elapsed = time.time() - start
                logger.error(f"[ERROR] {operation} - {elapsed:.2f}s - {str(e)}")
                raise
        return wrapper
    return decorator


class Timer:
    """
    Context manager for timing code blocks.
    
    Usage:
        with Timer("Embedding documents"):
            embeddings = embed_documents(docs)
    """
    
    def __init__(self, operation: str):
        self.operation = operation
        self.start_time = None
        self.elapsed = None
    
    def __enter__(self):
        self.start_time = time.time()
        logger.info(f"[START] {self.operation}...")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.elapsed = time.time() - self.start_time
        if exc_type is None:
            logger.info(f"[DONE] {self.operation} - {self.elapsed:.2f}s")
        else:
            logger.error(f"[ERROR] {self.operation} - {self.elapsed:.2f}s - {str(exc_val)}")
        return False


def log_info(message: str):
    """Log an info message."""
    logger.info(message)


def log_error(message: str):
    """Log an error message."""
    logger.error(message)


def log_debug(message: str):
    """Log a debug message."""
    logger.debug(message)