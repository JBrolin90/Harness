"""Unit tests for logger.py - debug logging module."""
import pytest
import sys
import os
import logging
import tempfile
from unittest.mock import patch, MagicMock
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

# Import the module under test
import logger as logger_module


class TestSetupDebugLogging:
    """Tests for setup_debug_logging() function."""

    def setup_method(self):
        """Reset module state before each test."""
        logger_module._logger = None
        logger_module._debug_enabled = False
        # Remove any handlers that may have been added
        if logging.getLogger("harness").handlers:
            logging.getLogger("harness").handlers.clear()

    def teardown_method(self):
        """Clean up after each test."""
        logger_module._logger = None
        logger_module._debug_enabled = False
        if logging.getLogger("harness").handlers:
            logging.getLogger("harness").handlers.clear()

    def test_setup_debug_logging_disabled_returns_noop_logger(self):
        """When enabled=False, should return a logger with NullHandler."""
        result = logger_module.setup_debug_logging(enabled=False)
        
        assert isinstance(result, logging.Logger)
        # Should have NullHandler
        assert any(isinstance(h, logging.NullHandler) for h in result.handlers)

    def test_setup_debug_logging_enabled_creates_file_handler(self):
        """When enabled=True, should configure file handler."""
        with tempfile.NamedTemporaryFile(suffix='.log', delete=False) as f:
            log_path = f.name
        
        try:
            result = logger_module.setup_debug_logging(enabled=True, log_path=log_path)
            
            assert isinstance(result, logging.Logger)
            assert result.level == logging.DEBUG
            assert any(isinstance(h, logging.FileHandler) for h in result.handlers)
        finally:
            os.unlink(log_path)

    def test_setup_debug_logging_enabled_sets_debug_flag(self):
        """When enabled=True, _debug_enabled should be True."""
        logger_module.setup_debug_logging(enabled=True)
        
        assert logger_module._debug_enabled is True

    def test_setup_debug_logging_disabled_sets_debug_flag_false(self):
        """When enabled=False, _debug_enabled should be False."""
        logger_module.setup_debug_logging(enabled=False)
        
        assert logger_module._debug_enabled is False

    def test_setup_debug_logging_custom_log_path(self):
        """Should use custom log_path when provided."""
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_path = os.path.join(tmpdir, "custom.log")
            
            result = logger_module.setup_debug_logging(enabled=True, log_path=custom_path)
            
            assert any(isinstance(h, logging.FileHandler) and h.baseFilename == custom_path 
                      for h in result.handlers)

    def test_setup_debug_logging_idempotent(self):
        """Calling setup multiple times should not add duplicate handlers."""
        with tempfile.NamedTemporaryFile(suffix='.log', delete=False) as f:
            log_path = f.name
        
        try:
            logger_module.setup_debug_logging(enabled=True, log_path=log_path)
            logger_module.setup_debug_logging(enabled=True, log_path=log_path)
            
            file_handlers = [h for h in logger_module._logger.handlers 
                           if isinstance(h, logging.FileHandler)]
            assert len(file_handlers) == 1
        finally:
            os.unlink(log_path)

    def test_setup_debug_logging_returns_same_logger_instance(self):
        """Should return the same logger instance on subsequent calls."""
        logger1 = logger_module.setup_debug_logging(enabled=False)
        logger2 = logger_module.setup_debug_logging(enabled=False)
        
        assert logger1 is logger2


class TestIsDebugEnabled:
    """Tests for is_debug_enabled() function."""

    def setup_method(self):
        """Reset module state before each test."""
        logger_module._logger = None
        logger_module._debug_enabled = False

    def teardown_method(self):
        """Clean up after each test."""
        logger_module._logger = None
        logger_module._debug_enabled = False

    def test_is_debug_enabled_false_by_default(self):
        """Should return False when not explicitly enabled."""
        result = logger_module.is_debug_enabled()
        
        assert result is False

    def test_is_debug_enabled_true_after_setup(self):
        """Should return True after setup_debug_logging(enabled=True)."""
        logger_module.setup_debug_logging(enabled=True)
        
        assert logger_module.is_debug_enabled() is True

    def test_is_debug_enabled_false_when_disabled(self):
        """Should return False after setup_debug_logging(enabled=False)."""
        logger_module.setup_debug_logging(enabled=True)
        logger_module.setup_debug_logging(enabled=False)
        
        assert logger_module.is_debug_enabled() is False


class TestGetLogger:
    """Tests for get_logger() function."""

    def setup_method(self):
        """Reset module state before each test."""
        logger_module._logger = None
        logger_module._debug_enabled = False

    def teardown_method(self):
        """Clean up after each test."""
        logger_module._logger = None
        logger_module._debug_enabled = False

    def test_get_logger_returns_logger_instance(self):
        """Should return a logging.Logger instance."""
        result = logger_module.get_logger()
        
        assert isinstance(result, logging.Logger)

    def test_get_logger_lazy_initialization(self):
        """Should initialize logger on first call."""
        assert logger_module._logger is None
        
        logger_module.get_logger()
        
        assert logger_module._logger is not None

    def test_get_logger_respects_env_var(self):
        """Should check HARNESS_DEBUG env var for lazy initialization."""
        with patch.dict(os.environ, {"HARNESS_DEBUG": "1"}):
            logger_module._logger = None
            logger_module._debug_enabled = False
            
            logger_module.get_logger()
            
            assert logger_module._debug_enabled is True
        
        # Clean up env
        if "HARNESS_DEBUG" in os.environ:
            del os.environ["HARNESS_DEBUG"]

    def test_get_logger_returns_same_instance(self):
        """Should return the same logger instance on subsequent calls."""
        logger1 = logger_module.get_logger()
        logger2 = logger_module.get_logger()
        
        assert logger1 is logger2


class TestLogFunctions:
    """Tests for debug(), info(), warning(), error() convenience functions."""

    def setup_method(self):
        """Reset module state before each test."""
        logger_module._logger = None
        logger_module._debug_enabled = False

    def teardown_method(self):
        """Clean up after each test."""
        logger_module._logger = None
        logger_module._debug_enabled = False

    def test_debug_function_logs_debug_level(self):
        """debug() should log at DEBUG level."""
        with tempfile.NamedTemporaryFile(suffix='.log', delete=False) as f:
            log_path = f.name
        
        try:
            logger_module.setup_debug_logging(enabled=True, log_path=log_path)
            logger_module.debug("Test debug message", module="test_module")
            
            with open(log_path, 'r') as f:
                content = f.read()
            
            assert "Test debug message" in content
            assert "[test_module]" in content
        finally:
            os.unlink(log_path)

    def test_info_function_logs_info_level(self):
        """info() should log at INFO level."""
        with tempfile.NamedTemporaryFile(suffix='.log', delete=False) as f:
            log_path = f.name
        
        try:
            logger_module.setup_debug_logging(enabled=True, log_path=log_path)
            logger_module.info("Test info message", module="test_module")
            
            with open(log_path, 'r') as f:
                content = f.read()
            
            assert "Test info message" in content
        finally:
            os.unlink(log_path)

    def test_warning_function_logs_warning_level(self):
        """warning() should log at WARNING level."""
        with tempfile.NamedTemporaryFile(suffix='.log', delete=False) as f:
            log_path = f.name
        
        try:
            logger_module.setup_debug_logging(enabled=True, log_path=log_path)
            logger_module.warning("Test warning message", module="test_module")
            
            with open(log_path, 'r') as f:
                content = f.read()
            
            assert "Test warning message" in content
        finally:
            os.unlink(log_path)

    def test_error_function_logs_error_level(self):
        """error() should log at ERROR level."""
        with tempfile.NamedTemporaryFile(suffix='.log', delete=False) as f:
            log_path = f.name
        
        try:
            logger_module.setup_debug_logging(enabled=True, log_path=log_path)
            logger_module.error("Test error message", module="test_module")
            
            with open(log_path, 'r') as f:
                content = f.read()
            
            assert "Test error message" in content
        finally:
            os.unlink(log_path)

    def test_log_functions_use_harness_as_default_module(self):
        """Log functions should default to 'harness' module name."""
        with tempfile.NamedTemporaryFile(suffix='.log', delete=False) as f:
            log_path = f.name
        
        try:
            logger_module.setup_debug_logging(enabled=True, log_path=log_path)
            logger_module.debug("Test message")
            
            with open(log_path, 'r') as f:
                content = f.read()
            
            assert "[harness]" in content
        finally:
            os.unlink(log_path)

    def test_log_functions_preserve_logger_name(self):
        """Log functions should restore logger name after logging."""
        with tempfile.NamedTemporaryFile(suffix='.log', delete=False) as f:
            log_path = f.name
        
        try:
            logger_module.setup_debug_logging(enabled=True, log_path=log_path)
            logger_module.debug("Message 1", module="module1")
            logger_module.debug("Message 2", module="module2")
            
            # Logger name should be 'harness' after operations
            assert logger_module.get_logger().name == "harness"
        finally:
            os.unlink(log_path)


class TestDefaultLogPath:
    """Tests for default log path behavior."""

    def setup_method(self):
        """Reset module state before each test."""
        logger_module._logger = None
        logger_module._debug_enabled = False

    def teardown_method(self):
        """Clean up after each test."""
        logger_module._logger = None
        logger_module._debug_enabled = False

    def test_default_log_path_uses_env_var(self):
        """Should use HARNESS_DEBUG_LOG env var when set."""
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_path = os.path.join(tmpdir, "env.log")
            with patch.dict(os.environ, {"HARNESS_DEBUG_LOG": custom_path}):
                logger_module.setup_debug_logging(enabled=True)
                
                file_handlers = [h for h in logger_module._logger.handlers 
                               if isinstance(h, logging.FileHandler)]
                assert any(h.baseFilename == custom_path for h in file_handlers)
            
            # Clean up env
            if "HARNESS_DEBUG_LOG" in os.environ:
                del os.environ["HARNESS_DEBUG_LOG"]

    def test_default_log_path_falls_back_to_project_dir(self):
        """Should fall back to harness_debug.log in project directory."""
        # When env var is not set, should use project dir
        if "HARNESS_DEBUG_LOG" in os.environ:
            del os.environ["HARNESS_DEBUG_LOG"]
        
        logger_module.setup_debug_logging(enabled=True)
        
        file_handlers = [h for h in logger_module._logger.handlers 
                       if isinstance(h, logging.FileHandler)]
        # Should have created a file handler in project dir
        assert any("harness_debug.log" in h.baseFilename for h in file_handlers)


class TestLogFormat:
    """Tests for log message format."""

    def setup_method(self):
        """Reset module state before each test."""
        logger_module._logger = None
        logger_module._debug_enabled = False

    def teardown_method(self):
        """Clean up after each test."""
        logger_module._logger = None
        logger_module._debug_enabled = False

    def test_log_format_includes_timestamp(self):
        """Log messages should include timestamp."""
        with tempfile.NamedTemporaryFile(suffix='.log', delete=False) as f:
            log_path = f.name
        
        try:
            logger_module.setup_debug_logging(enabled=True, log_path=log_path)
            logger_module.debug("Test message")
            
            with open(log_path, 'r') as f:
                content = f.read()
            
            # Should have timestamp in format YYYY-MM-DD HH:MM:SS
            import re
            assert re.search(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', content)
        finally:
            os.unlink(log_path)

    def test_log_format_includes_module_name(self):
        """Log messages should include module name in brackets."""
        with tempfile.NamedTemporaryFile(suffix='.log', delete=False) as f:
            log_path = f.name
        
        try:
            logger_module.setup_debug_logging(enabled=True, log_path=log_path)
            logger_module.debug("Test", module="mymodule")
            
            with open(log_path, 'r') as f:
                content = f.read()
            
            assert "[mymodule]" in content
        finally:
            os.unlink(log_path)

    def test_log_format_includes_level(self):
        """Log messages should include log level."""
        with tempfile.NamedTemporaryFile(suffix='.log', delete=False) as f:
            log_path = f.name
        
        try:
            logger_module.setup_debug_logging(enabled=True, log_path=log_path)
            logger_module.warning("Test warning")
            
            with open(log_path, 'r') as f:
                content = f.read()
            
            assert "WARNING:" in content
        finally:
            os.unlink(log_path)