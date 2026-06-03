"""Unit tests for controller.py - SessionManager."""
import pytest
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))


class TestSessionManagerInit:
    """Tests for SessionManager.__init__()"""

    @patch('session.session_manager.ProviderManager')
    def test_init_creates_instance_state(self, mock_pm_class):
        """__init__() should create instance attributes."""
        mock_pm_instance = MagicMock()
        mock_pm_class.return_value = mock_pm_instance
        mock_provider = MagicMock()
        mock_provider.name = "test-provider"
        mock_provider.provider_type = "minimax"
        mock_provider.attributes = {}
        mock_pm_instance.get_provider.return_value = mock_provider

        from session.session_manager import SessionManager
        session = SessionManager()

        assert hasattr(session, 'current_provider')
        assert hasattr(session, 'system_prompt_manager')

    @patch('session.session_manager.ProviderManager')
    def test_init_creates_system_prompt_manager(self, mock_pm_class):
        """__init__() should create SystemPromptManager."""
        mock_pm_instance = MagicMock()
        mock_pm_class.return_value = mock_pm_instance
        mock_provider = MagicMock()
        mock_provider.provider_type = "minimax"
        mock_provider.attributes = {}
        mock_pm_instance.get_provider.return_value = mock_provider

        from session.session_manager import SessionManager
        session = SessionManager()

        assert hasattr(session, 'system_prompt_manager')
        assert hasattr(session.system_prompt_manager, 'get_system_prompt')


class TestSessionManagerRunTask:
    """Tests for SessionManager.run_task()"""

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

    @patch('session.session_manager.Task')
    def test_run_task_returns_run_result(self, mock_task_class, session_instance):
        """run_task() should return the result from Task.run()."""
        mock_task_instance = MagicMock()
        mock_task_instance.run.return_value = "Final answer"
        mock_task_class.return_value = mock_task_instance

        result = session_instance.run_task("Hello Bob")

        assert result == "Final answer"
        mock_task_instance.run.assert_called_once()

    @patch('session.session_manager.Task')
    def test_run_task_passes_parameters_to_run(self, mock_task_class, session_instance):
        """run_task() should pass prompt and system_prompt to run."""
        mock_task_instance = MagicMock()
        mock_task_instance.run.return_value = "Done"
        mock_task_class.return_value = mock_task_instance
        session_instance.system_prompt_manager.get_system_prompt = MagicMock(return_value="System prompt")

        session_instance.run_task("User prompt")

        call_kwargs = mock_task_instance.run.call_args.kwargs
        assert 'prompt' in call_kwargs
        assert 'system_prompt' in call_kwargs
        assert 'consult_llm' in call_kwargs
        assert 'provider' in call_kwargs

    @patch('session.session_manager.Task')
    def test_run_task_with_custom_consult_llm(self, mock_task_class, session_instance):
        """run_task() should pass custom call_llm to run."""
        mock_task_instance = MagicMock()
        mock_task_instance.run.return_value = "Done"
        mock_task_class.return_value = mock_task_instance
        session_instance.system_prompt_manager.get_system_prompt = MagicMock(return_value="System prompt")
        custom_consult_llm = MagicMock()
        
        session_instance.run_task("Hello", consult_llm=custom_consult_llm)

        call_kwargs = mock_task_instance.run.call_args.kwargs
        assert call_kwargs['consult_llm'] is custom_consult_llm

    @patch('session.session_manager.ToolManager')
    @patch('session.session_manager.Task')
    def test_run_task_with_max_iterations(self, mock_task_class, mock_tm_class, session_instance):
        """run_task() should pass max_iterations to Task constructor."""
        mock_task_instance = MagicMock()
        mock_task_instance.run.return_value = "Done"
        mock_task_class.return_value = mock_task_instance
        session_instance.system_prompt_manager.get_system_prompt = MagicMock(return_value="System prompt")

        session_instance.run_task("Hello", max_iterations=10)

        # Verify Task was created with max_iterations=10
        mock_task_class.assert_called_once()
        _, kwargs = mock_task_class.call_args
        assert kwargs.get('max_iterations') == 10 or mock_task_class.call_args[0][1] == 10
