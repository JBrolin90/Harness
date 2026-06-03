"""Unit tests for bob.py - CLI entry point."""
import pytest
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))

from response import LLMResponse, NoToolFound


class TestSessionManagerImport:
    """Tests for importing and basic instantiation."""

    @patch('session_manager.ProviderManager')
    def test_session_manager_class_exists(self, mock_pm_class):
        """SessionManager class should be accessible from controller module."""
        mock_pm_instance = MagicMock()
        mock_pm_class.return_value = mock_pm_instance
        mock_provider = MagicMock()
        mock_provider.provider_type = "minimax"
        mock_provider.attributes = {}
        mock_pm_instance.get_provider.return_value = mock_provider

        from session_manager import SessionManager
        assert SessionManager is not None

    @patch('session_manager.ProviderManager')
    def test_session_manager_default_provider(self, mock_pm_class):
        """SessionManager() should default to cloud-pro provider."""
        mock_pm_instance = MagicMock()
        mock_pm_class.return_value = mock_pm_instance
        mock_provider = MagicMock()
        mock_provider.name = "cloud-pro"
        mock_provider.model = "MiniMax-M2"
        mock_provider.provider_type = "minimax"
        mock_provider.attributes = {}
        mock_pm_instance.get_provider.return_value = mock_provider

        from session_manager import SessionManager
        session = SessionManager()

        mock_pm_instance.get_provider.assert_called_with("cloud-pro")
        assert session.current_provider.name == "cloud-pro"

    @patch('session_manager.ProviderManager')
    def test_session_manager_named_provider(self, mock_pm_class):
        """SessionManager('local-coder') should use specified provider."""
        mock_pm_instance = MagicMock()
        mock_pm_class.return_value = mock_pm_instance
        mock_provider = MagicMock()
        mock_provider.name = "local-coder"
        mock_provider.provider_type = "minimax"
        mock_provider.attributes = {}
        mock_pm_instance.get_provider.return_value = mock_provider

        from session_manager import SessionManager
        session = SessionManager("local-coder")

        mock_pm_instance.get_provider.assert_called_with("local-coder")
        assert session.current_provider.name == "local-coder"


class TestSessionManagerRunTask:
    """Tests for SessionManager.run_task() behavior."""

    @pytest.fixture
    def session_instance(self):
        """Create a mocked session instance."""
        with patch('session_manager.ProviderManager') as mock_pm_class:
            mock_pm_instance = MagicMock()
            mock_pm_class.return_value = mock_pm_instance
            mock_provider = MagicMock()
            mock_provider.name = "test"
            mock_provider.model = "test-model"
            mock_provider.provider_type = "minimax"
            mock_provider.attributes = {}
            mock_pm_instance.get_provider.return_value = mock_provider

            from session_manager import SessionManager
            session = SessionManager()
            session.current_provider = MagicMock()
            yield session

    @patch('iteration_handler.IterationHandler.execute')
    def test_run_task_returns_response(self, mock_execute, session_instance):
        """run_task() should return a response string."""
        mock_execute.return_value = "Final response from Bob"

        result = session_instance.run_task("Hello")

        assert result == "Final response from Bob"

    @patch('iteration_handler.IterationHandler.execute')
    def test_run_task_calls_execute(self, mock_execute, session_instance):
        """run_task() dispatches to IterationHandler.execute()."""
        mock_execute.return_value = "Done"

        session_instance.run_task("Read the file")

        mock_execute.assert_called_once()


class TestSessionManagerReset:
    """Tests for SessionManager.reset()."""

    @patch('session_manager.ProviderManager')
    def test_reset_is_noop(self, mock_pm_class):
        """reset() is a no-op."""
        mock_pm_instance = MagicMock()
        mock_pm_class.return_value = mock_pm_instance
        mock_provider = MagicMock()
        mock_provider.provider_type = "minimax"
        mock_provider.attributes = {}
        mock_pm_instance.get_provider.return_value = mock_provider

        from session_manager import SessionManager
        session = SessionManager()

        # Should not raise
        session.reset()