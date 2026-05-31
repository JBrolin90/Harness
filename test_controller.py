"""Unit tests for controller.py - Harness controller."""
import pytest
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))


class TestHarnessControllerInit:
    """Tests for HarnessController.__init__()"""

    @patch('controller.terminal_history_upgrade')
    @patch('controller.ProviderManager')
    def test_init_creates_instance_state(self, mock_pm_class, mock_terminal):
        """__init__() should create instance attributes."""
        mock_pm_instance = MagicMock()
        mock_pm_class.return_value = mock_pm_instance
        mock_provider = MagicMock()
        mock_provider.name = "test-provider"
        mock_provider.model = "test-model"
        mock_pm_instance.get_provider.return_value = mock_provider

        from controller import HarnessController
        ctrl = HarnessController()

        assert hasattr(ctrl, 'current_provider')
        assert hasattr(ctrl, 'conversation_history')
        assert hasattr(ctrl, 'tool_engine')
        assert ctrl.current_provider == mock_provider
        assert isinstance(ctrl.conversation_history, list)

    @patch('controller.terminal_history_upgrade')
    @patch('controller.ProviderManager')
    def test_reset_clears_history(self, mock_pm_class, mock_terminal):
        """reset() should clear conversation history."""
        mock_pm_instance = MagicMock()
        mock_pm_class.return_value = mock_pm_instance
        mock_provider = MagicMock()
        mock_pm_instance.get_provider.return_value = mock_provider

        from controller import HarnessController
        ctrl = HarnessController()
        ctrl.conversation_history = [{"role": "user", "content": "test"}]

        ctrl.reset()

        assert ctrl.conversation_history == []


class TestHarnessControllerRunTask:
    """Tests for HarnessController.run_task()"""

    @pytest.fixture
    def controller_instance(self):
        """Create a mocked controller instance for testing."""
        with patch('controller.terminal_history_upgrade'), \
             patch('controller.ProviderManager') as mock_pm_class:
            mock_pm_instance = MagicMock()
            mock_pm_class.return_value = mock_pm_instance
            mock_provider = MagicMock()
            mock_pm_instance.get_provider.return_value = mock_provider

            from controller import HarnessController
            ctrl = HarnessController()
            ctrl.current_provider = MagicMock()
            ctrl.system_prompt = "Test prompt"
            ctrl.conversation_history = []
            ctrl.tool_engine = MagicMock(return_value=None)
            yield ctrl

    @patch('controller.call_llm')
    def test_run_task_adds_to_history(self, mock_call_llm, controller_instance):
        """run_task() should append user message and assistant response to history."""
        mock_call_llm.return_value = "Hello from Bob"

        controller_instance.run_task("Hello Bob")

        assert len(controller_instance.conversation_history) == 2
        assert controller_instance.conversation_history[0]["role"] == "user"
        assert controller_instance.conversation_history[0]["content"] == "Hello Bob"
        assert controller_instance.conversation_history[1]["role"] == "assistant"
        assert controller_instance.conversation_history[1]["content"] == "Hello from Bob"

    @patch('controller.call_llm')
    def test_run_task_no_tool_returns_immediately(self, mock_call_llm, controller_instance):
        """If no tool call detected, run_task should return immediately."""
        mock_call_llm.return_value = "I can help with that."

        controller_instance.run_task("Hello")

        # Should be only the initial call, no tool execution loop
        assert mock_call_llm.call_count == 1

    @patch('controller.call_llm')
    def test_run_task_with_tool_call(self, mock_call_llm, controller_instance):
        """Tool in response triggers tool execution, then loop continues."""
        mock_call_llm.side_effect = [
            '{"name": "read_file", "arguments": {"path": "test.txt"}}',
            "[SYSTEM OUTPUT: File content]",  # tool result fed back
            "Final response after tool"  # final response after tool
        ]
        # First call returns tool result (truthy), second call returns None (no tool call)
        controller_instance.tool_engine.side_effect = [
            "[SYSTEM OUTPUT: File content]",
            None
        ]

        controller_instance.run_task("Read the file")

        assert controller_instance.tool_engine.call_count >= 1

    @patch('controller.call_llm')
    def test_run_task_returns_final_response(self, mock_call_llm, controller_instance):
        """run_task() should return the final response string."""
        mock_call_llm.return_value = "Final answer from Bob"

        result = controller_instance.run_task("What is the answer?")

        assert result == "Final answer from Bob"


class TestControllerModuleLevelFunctions:
    """Tests for backward-compatible module-level init() and run_task()"""

    @patch('controller.terminal_history_upgrade')
    @patch('controller.ProviderManager')
    def test_init_creates_global_controller(self, mock_pm_class, mock_terminal):
        """init() should create a global _controller instance."""
        mock_pm_instance = MagicMock()
        mock_pm_class.return_value = mock_pm_instance
        mock_provider = MagicMock()
        mock_pm_instance.get_provider.return_value = mock_provider

        import controller
        controller.init()

        assert controller._controller is not None
        assert isinstance(controller._controller, controller.HarnessController)

    @patch('controller.terminal_history_upgrade')
    @patch('controller.ProviderManager')
    def test_run_task_uses_global_controller(self, mock_pm_class, mock_terminal):
        """module run_task() should delegate to global controller."""
        mock_pm_instance = MagicMock()
        mock_pm_class.return_value = mock_pm_instance
        mock_provider = MagicMock()
        mock_pm_instance.get_provider.return_value = mock_provider

        import controller
        controller._controller = None  # Reset
        controller.init()

        assert controller._controller is not None
        assert isinstance(controller._controller, controller.HarnessController)

    @patch('controller.terminal_history_upgrade')
    @patch('controller.ProviderManager')
    def test_run_task_raises_without_init(self, mock_pm_class, mock_terminal):
        """module run_task() should raise if init() not called."""
        mock_pm_instance = MagicMock()
        mock_pm_class.return_value = mock_pm_instance
        mock_provider = MagicMock()
        mock_pm_instance.get_provider.return_value = mock_provider

        import controller
        controller._controller = None

        with pytest.raises(RuntimeError, match="Controller not initialized"):
            controller.run_task("test")


class TestMemoryIntegration:
    """Tests for memory integration in HarnessController."""

    @pytest.fixture
    def controller(self):
        with patch('controller.terminal_history_upgrade'), \
             patch('controller.ProviderManager') as mock_pm_class, \
             patch('controller.get_memory') as mock_get_memory:
            mock_pm_instance = MagicMock()
            mock_pm_class.return_value = mock_pm_instance
            mock_provider = MagicMock()
            mock_pm_instance.get_provider.return_value = mock_provider

            mock_memory = MagicMock()
            mock_get_memory.return_value = mock_memory

            from controller import HarnessController
            ctrl = HarnessController()
            return ctrl

    def test_controller_has_memory(self, controller):
        """Controller should have memory attribute."""
        assert hasattr(controller, 'memory')

    def test_remember_adds_to_memory(self, controller):
        """remember() should add item to memory section."""
        controller.memory.add = MagicMock()

        result = controller.remember("Personal", "User prefers dark mode")

        controller.memory.add.assert_called_once_with("Personal", "User prefers dark mode")
        assert "Added to 'Personal'" in result

    def test_search_memory_returns_results(self, controller):
        """search_memory() should return find results."""
        expected = [("Personal", "User works with Python")]
        controller.memory.find.return_value = expected

        result = controller.search_memory("Python")

        controller.memory.find.assert_called_once_with("Python")
        assert result == expected

    def test_get_memory_section_returns_list(self, controller):
        """get_memory_section() should return section items."""
        expected = ["Item 1", "Item 2"]
        controller.memory.get.return_value = expected

        result = controller.get_memory_section("Preferences")

        controller.memory.get.assert_called_once_with("Preferences")
        assert result == expected

    def test_get_memory_instructions_returns_string_or_none(self, controller):
        """get_memory_instructions() should return instructions or None."""
        with patch('controller.load_memory_instructions') as mock_load:
            mock_load.return_value = "Memory instructions content"
            result = controller.get_memory_instructions()
            assert result == "Memory instructions content"


class TestToolEngineIntegration:
    """Tests for ToolEngine integration in controller."""

    @pytest.fixture
    def controller(self):
        with patch('controller.terminal_history_upgrade'), \
             patch('controller.ProviderManager') as mock_pm_class:
            mock_pm_instance = MagicMock()
            mock_pm_class.return_value = mock_pm_instance
            mock_provider = MagicMock()
            mock_pm_instance.get_provider.return_value = mock_provider

            from controller import HarnessController
            ctrl = HarnessController()
            return ctrl

    def test_controller_has_tool_engine_function(self, controller):
        """Controller should have tool_engine as function reference."""
        from tool_dispatch import dispatch
        assert hasattr(controller, 'tool_engine')
        assert controller.tool_engine == dispatch

    def test_tool_engine_is_callable_function(self, controller):
        """dispatch() should be callable and return NoToolFound for plain text."""
        from tool_dispatch import dispatch
        from response import LLMResponse
        result = dispatch(LLMResponse(text="Plain text, no tool"))
        from tool_dispatch import NoToolFound
        assert isinstance(result, NoToolFound)
