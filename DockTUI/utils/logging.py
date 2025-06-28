"""Logging configuration for DockTUI."""

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging():
    """Configure logging to write to file in the user's home directory.

    Creates a .DockTUI/logs directory in the user's home directory and sets up
    file-based logging with detailed formatting. Only enables logging if DEBUG mode
    is active.

    Returns:
        Path: Path to the log file, or None if logging is disabled
    """
    # Check if debug mode is enabled (env var must be "1")
    if os.environ.get("DOCKTUI_DEBUG") != "1":
        # Disable all logging
        logging.getLogger().setLevel(logging.CRITICAL)
        return None

    log_dir = Path("./logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "DockTUI.log"

    file_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(threadName)s - %(message)s"
    )

    # Use RotatingFileHandler to limit log file size to 20MB with 2 backup files
    file_handler = RotatingFileHandler(
        log_file, maxBytes=20 * 1024 * 1024, backupCount=2  # 20MB
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)

    return log_file
