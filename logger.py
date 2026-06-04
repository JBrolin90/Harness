from __future__ import annotations

"""Debug logging module for Harness.

Provides configurable debug logging that writes to a file without
interfering with stdout output.

Usage:
    # Via environment variable
    HARNESS_DEBUG=1 python bob.py

    # Via CLI flag
    python bob.py --debug

    # With custom log path
    HARNESS_DEBUG_LOG=/tmp/harness.log HARNESS_DEBUG=1 python bob.py
"""
import logging  # noqa: E402
import os  # noqa: E402

# Module-level logger instance
_logger: logging.Logger | None = None
_debug_enabled: bool = False


def _get_default_log_path() -> str:
    """Get default log file path."""
    return os.environ.get(
        "HARNESS_DEBUG_LOG",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "harness_debug.log")
    )


def setup_debug_logging(enabled: bool = True, log_path: str | None = None) -> logging.Logger:
    """Set up debug logging to a file.

    Args:
        enabled: Whether debug logging is enabled.
        log_path: Path to log file. Defaults to harness_debug.log in project dir
                  or HARNESS_DEBUG_LOG env var if set.

    Returns:
        The configured logger instance.
    """
    global _logger, _debug_enabled

    # Ensure _logger is initialized
    if _logger is None:
        _logger = logging.getLogger("harness")
        _logger.addHandler(logging.NullHandler())  # Default: no-op handler

    if not enabled:
        _debug_enabled = False
        return _logger

    _debug_enabled = True

    # Configure file handler
    _logger.setLevel(logging.DEBUG)
    _logger.handlers.clear()

    log_file = log_path or _get_default_log_path()
    file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)

    # Format: [TIMESTAMP] [MODULE] LEVEL: message
    formatter = logging.Formatter(
        '[%(asctime)s] [%(name)s] %(levelname)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    _logger.addHandler(file_handler)

    return _logger


def is_debug_enabled() -> bool:
    """Check if debug logging is enabled."""
    return _debug_enabled


def get_logger() -> logging.Logger:
    """Get the harness logger instance.

    If debug logging hasn't been set up yet, returns a logger that
    will write to the default location if HARNESS_DEBUG is set.
    """
    global _logger

    if _logger is None:
        # Lazy initialization - check env var
        env_debug = os.environ.get("HARNESS_DEBUG", "0").lower() in ("1", "true", "yes")
        setup_debug_logging(enabled=env_debug)

    # assert _logger is not None - after setup, it's always initialized
    assert _logger is not None
    return _logger


# Convenience functions
def debug(message: str, module: str = "harness") -> None:
    """Log a debug message."""
    logger = get_logger()
    # Temporarily set the logger name to the module
    old_name = logger.name
    logger.name = module
    logger.debug(message)
    logger.name = old_name


def info(message: str, module: str = "harness") -> None:
    """Log an info message."""
    logger = get_logger()
    old_name = logger.name
    logger.name = module
    logger.info(message)
    logger.name = old_name


def warning(message: str, module: str = "harness") -> None:
    """Log a warning message."""
    logger = get_logger()
    old_name = logger.name
    logger.name = module
    logger.warning(message)
    logger.name = old_name


def error(message: str, module: str = "harness") -> None:
    """Log an error message."""
    logger = get_logger()
    old_name = logger.name
    logger.name = module
    logger.error(message)
    logger.name = old_name
