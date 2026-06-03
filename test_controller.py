"""Unit tests for controller.py - SessionManager."""
import pytest
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))


class TestSessionManagerInit:
    """Tests for SessionManager.__init__()"""

    @patch('controller.ProviderManager')
    def test_init_creates_instance_state(self, mock_pm_class):
        """__init__() should create instance attributes."""
        mock_pm_instance = MagicMock()
        mock_pm_class.return_value = mock_pm_instance
        mock_provider = MagicMock()
        mock_provider.name = "test-provider"
        mock_provider.provider_type = "minimax"
        mock_provider.attributes = {}
        mock_pm_instance.get_provider.return_value = mock_provider

        from controller import SessionManager
        session = SessionManager()

        assert hasattr(session, 'current_provider')
        assert hasattr(session, 'system_prompt_manager')

    @patch('controller.ProviderManager')
    def test_init_creates_system_prompt_manager(self, mock_pm_class):
        """__init__() should create SystemPromptManager."""
        mock_pm_instance = MagicMock()
        mock_pm_class.return_value = mock_pm_instance
        mock_provider = MagicMock()
        mock_provider.provider_type = "minimax"
        mock_provider.attributes = {}
        mock_pm_instance.get_provider.return_value = mock_provider

        from controller import SessionManager
        session = SessionManager()

        assert hasattr(session, 'system_prompt_manager')
        assert hasattr(session.system_prompt_manager, 'get_system_prompt')


class TestSessionManagerRunTask:
    """Tests for SessionManager.run_task()"""

    @pytest.fixture
    def session_instance(self):
        """Create a mocked session instance for testing."""
        with patch('controller.ProviderManager') as mock_pm_class:
            mock_pm_instance = MagicMock()
            mock_pm_class.return_value = mock_pm_instance
            mock_provider = MagicMock()
            mock_provider.name = "test"
            mock_provider.model = "test-model"
            mock_provider.provider_type = "minimax"
            mock_provider.attributes = {}
            mock_pm_instance.get_provider.return_value = mock_provider

            from controller import SessionManager
            session = SessionManager()
            session.current_provider = MagicMock()
            yield session

    @patch('iteration_handler.IterationHandler.execute')
    def test_run_task_returns_execute_result(self, mock_execute, session_instance):
        """run_task() should return the result from IterationHandler.execute()."""
        mock_execute.return_value = "Final answer"

        result = session_instance.run_task("Hello Bob")

        assert result == "Final answer"
        mock_execute.assert_called_once()

    @patch('iteration_handler.IterationHandler.execute')
    def test_run_task_passes_parameters_to_execute(self, mock_execute, session_instance):
        """run_task() should pass prompt and system_prompt to execute."""
        mock_execute.return_value = "Done"
        session_instance.system_prompt_manager.get_system_prompt = MagicMock(return_value="System prompt")

        session_instance.run_task("User prompt")

        call_kwargs = mock_execute.call_args.kwargs
        assert 'prompt' in call_kwargs
        assert 'system_prompt' in call_kwargs
        assert 'call_llm' in call_kwargs

    @patch('iteration_handler.IterationHandler.execute')
    def test_run_task_with_custom_call_llm(self, mock_execute, session_instance):
        """run_task() should pass custom call_llm to execute."""
        mock_execute.return_value = "Done"
        session_instance.system_prompt_manager.get_system_prompt = MagicMock(return_value="System prompt")
        custom_call_llm = MagicMock()

        session_instance.run_task("Hello", call_llm=custom_call_llm)

        call_kwargs = mock_execute.call_args.kwargs
        assert call_kwargs['call_llm'] is custom_call_llm

    @patch('iteration_handler.IterationHandler.execute')
    def test_run_task_with_max_iterations(self, mock_execute, session_instance):
        """run_task() should pass max_iterations to IterationHandler constructor."""
        mock_execute.return_value = "Done"
        session_instance.system_prompt_manager.get_system_prompt = MagicMock(return_value="System prompt")

        with patch('controller.IterationHandler') as mock_handler_class:
            mock_handler_instance = MagicMock()
            mock_handler_instance.execute.return_value = "Done"
            mock_handler_class.return_value = mock_handler_instance

            session_instance.run_task("Hello", max_iterations=10)

            mock_handler_class.assert_called_with(session_instance.current_provider, 10)