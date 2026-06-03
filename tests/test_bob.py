"""Unit tests for bob.py - main entry point."""
import pytest
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))


class TestSessionManagerImport:
    """Tests for SessionManager import and initialization."""

    @patch('session.session_manager.ProviderManager')
    def test_session_manager_class_exists(self, mock_pm_class):
        """SessionManager should be importable."""
        mock_pm_instance = MagicMock()
        mock_pm_class.return_value = mock_pm_instance
        mock_provider = MagicMock()
        mock_provider.provider_type = "minimax"
        mock_provider.attributes = {}
        mock_pm_instance.get_provider.return_value = mock_provider

        from session.session_manager import SessionManager
        session = SessionManager()

        assert session is not None

    @patch('session.session_manager.ProviderManager')
    def test_session_manager_default_provider(self, mock_pm_class):
        """SessionManager should default to cloud-pro provider."""
        mock_pm_instance = MagicMock()
        mock_pm_class.return_value = mock_pm_instance
        mock_provider = MagicMock()
        mock_provider.name = "cloud-pro"
        mock_provider.provider_type = "minimax"
        mock_provider.attributes = {}
        mock_pm_instance.get_provider.return_value = mock_provider

        from session.session_manager import SessionManager
        session = SessionManager()

        mock_pm_instance.get_provider.assert_called_with("cloud-pro")

    @patch('session.session_manager.ProviderManager')
    def test_session_manager_named_provider(self, mock_pm_class):
        """SessionManager should accept provider_name parameter."""
        mock_pm_instance = MagicMock()
        mock_pm_class.return_value = mock_pm_instance
        mock_provider = MagicMock()
        mock_provider.name = "my-provider"
        mock_provider.provider_type = "minimax"
        mock_provider.attributes = {}
        mock_pm_instance.get_provider.return_value = mock_provider

        from session.session_manager import SessionManager
        session = SessionManager(provider_name="my-provider")

        mock_pm_instance.get_provider.assert_called_with("my-provider")


class TestSessionManagerRunTask:
    """Tests for SessionManager.run_task() behavior."""

    @pytest.fixture
    def session_instance(self):
        """Create a mocked session instance for testing."""
        with patch('session.session_manager.ProviderManager') as mock_pm_class:
            mock_pm_instance = MagicMock()
            mock_pm_class.return_value = mock_pm_instance
            mock_provider = MagicMock()
            mock_provider.name = "test"
            mock_provider.model = "test-model"
            mock_provider.provider_type = "minimax"
            mock_provider.attributes = {}
            mock_pm_instance.get_provider.return_value = mock_provider

            from session.session_manager import SessionManager
            session = SessionManager()
            session.current_provider = MagicMock()
            yield session

    @patch('task.Task.run')
    def test_run_task_returns_response(self, mock_run, session_instance):
        """run_task() should return a response string."""
        mock_run.return_value = "Final response from Bob"

        result = session_instance.run_task("Hello")

        assert result == "Final response from Bob"

    @patch('task.Task.run')
    def test_run_task_calls_execute(self, mock_run, session_instance):
        """run_task() dispatches to Task.run()."""
        mock_run.return_value = "Done"

        session_instance.run_task("Read the file")

        mock_run.assert_called_once()


class TestSessionManagerReset:
    """Tests for SessionManager.reset()."""

    @patch('session.session_manager.ProviderManager')
    def test_reset_is_noop(self, mock_pm_class):
        """reset() is a no-op."""
        mock_pm_instance = MagicMock()
        mock_pm_class.return_value = mock_pm_instance
        mock_provider = MagicMock()
        mock_provider.provider_type = "minimax"
        mock_provider.attributes = {}
        mock_pm_instance.get_provider.return_value = mock_provider

        from session.session_manager import SessionManager
        session = SessionManager()

        # Should not raise
        session.reset()
