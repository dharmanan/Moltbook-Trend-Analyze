"""Logging utility for MoltBridge Agent."""

import logging
import os
from datetime import datetime


def setup_logger(name: str = "moltbridge") -> logging.Logger:
    """Configure and return a logger instance."""
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level, logging.INFO))

    if not logger.handlers:
        # Console handler
        ch = logging.StreamHandler()
        ch.setLevel(getattr(logging, log_level, logging.INFO))

        formatter = logging.Formatter(
            "%(asctime)s | %(name)s | %(levelname)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        ch.setFormatter(formatter)
        logger.addHandler(ch)

        # File handler
        log_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data", "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, f"{datetime.now():%Y-%m-%d}.log")

        fh = logging.FileHandler(log_file)
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(formatter)
        logger.addHandler(fh)

    return logger


log = setup_logger()
