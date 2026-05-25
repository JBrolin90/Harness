import pytest
import sys
import os
import re
import tempfile
from unittest.mock import patch, MagicMock

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))


class TestHarnessControllerInit:
    """Tests for HarnessController.__init__()"""

    @patch('controller.terminal_history_upgrade')
    @patch('controller.ProviderManager')
    def test_init_creates_instance_state(self, mock_pm_class, mock_terminal):
        """__init__() should create instance attributes, not module globals"""
        mock_pm_instance = MagicMock()
        mock_pm_class.return_value = mock_pm_instance
        mock_provider = MagicMock()
        mock_provider.name = "test-provider"
        mock_provider.model = "test-model"
        mock_pm_instance.get_provider.return_value = mock_provider

        with patch('controller.AGENT_md_INGESTIOR', return_value=""):
            from controller import HarnessController
            ctrl = HarnessController()

            assert hasattr(ctrl, 'current_provider')
            assert hasattr(ctrl, 'system_prompt')
            assert hasattr(ctrl, 'session')
            assert ctrl.current_provider == mock_provider
            assert isinstance(ctrl.session.conversation_history, list)

    @patch('controller.terminal_history_upgrade')
    @patch('controller.ProviderManager')
    def test_init_raises_when_no_provider(self, mock_pm_class, mock_terminal):
        """__init__() should raise RuntimeError if no provider found"""
        mock_pm_instance = MagicMock()
        mock_pm_class.return_value = mock_pm_instance
        mock_pm_instance.get_provider.return_value = None

        from controller import HarnessController
        with pytest.raises(RuntimeError, match="No LLM provider found"):
            HarnessController()

    @patch('controller.terminal_history_upgrade')
    @patch('controller.ProviderManager')
    @patch('controller.AGENT_md_INGESTIOR')
    def test_init_system_prompt_contains_tools(self, mock_agent, mock_pm_class, mock_terminal):
        """__init__() should build system prompt with tools instructions"""
        mock_pm_instance = MagicMock()
        mock_pm_class.return_value = mock_pm_instance
        mock_provider = MagicMock()
        mock_pm_instance.get_provider.return_value = mock_provider
        mock_agent.return_value = ""

        from controller import HarnessController
        ctrl = HarnessController()

        assert "AVAILABLE TOOLS" in ctrl.system_prompt
        assert "!READ" in ctrl.system_prompt
        assert "!WRITE" in ctrl.system_prompt

    @patch('controller.terminal_history_upgrade')
    @patch('controller.ProviderManager')
    @patch('controller.AGENT_md_INGESTIOR')
    def test_init_selects_named_provider(self, mock_agent, mock_pm_class, mock_terminal):
        """__init__() should use the provider specified by name"""
        mock_pm_instance = MagicMock()
        mock_pm_class.return_value = mock_pm_instance
        mock_provider_local = MagicMock()
        mock_provider_local.name = "local-coder"
        mock_pm_instance.get_provider.return_value = mock_provider_local

        from controller import HarnessController
        ctrl = HarnessController("local-coder")

        mock_pm_instance.get_provider.assert_called_with("local-coder")
        assert ctrl.current_provider == mock_provider_local

    @patch('controller.terminal_history_upgrade')
    @patch('controller.ProviderManager')
    @patch('controller.AGENT_md_INGESTIOR')
    def test_reset_clears_history(self, mock_agent, mock_pm_class, mock_terminal):
        """reset() should clear conversation history"""
        mock_pm_instance = MagicMock()
        mock_pm_class.return_value = mock_pm_instance
        mock_provider = MagicMock()
        mock_pm_instance.get_provider.return_value = mock_provider
        mock_agent.return_value = ""

        from controller import HarnessController
        ctrl = HarnessController()
        ctrl.session.conversation_history = [{"role": "user", "content": "test"}]

        ctrl.reset()

        assert ctrl.session.conversation_history == []


class TestHarnessControllerRunTask:
    """Tests for HarnessController.run_task()"""

    @pytest.fixture
    def controller(self):
        """Create a mocked controller instance for testing"""
        with patch('controller.terminal_history_upgrade'), \
             patch('controller.ProviderManager') as mock_pm_class, \
             patch('controller.AGENT_md_INGESTIOR', return_value=""):
            mock_pm_instance = MagicMock()
            mock_pm_class.return_value = mock_pm_instance
            mock_provider = MagicMock()
            mock_pm_instance.get_provider.return_value = mock_provider

            from controller import HarnessController
            # Disable context tracking for basic tool execution tests
            ctrl = HarnessController(enable_context=False)
            ctrl.current_provider = MagicMock()
            ctrl.system_prompt = "Test prompt"
            ctrl.session.conversation_history = []
            yield ctrl

    @patch('controller.call_llm')
    def test_run_task_adds_to_history(self, mock_call_llm, controller):
        """run_task() should append user message and assistant response to history"""
        mock_call_llm.return_value = "Hello from Bob"

        controller.run_task("Hello Bob")

        assert len(controller.session.conversation_history) == 2
        assert controller.session.conversation_history[0]["role"] == "user"
        assert controller.session.conversation_history[0]["content"] == "Hello Bob"
        assert controller.session.conversation_history[1]["role"] == "assistant"
        assert controller.session.conversation_history[1]["content"] == "Hello from Bob"

    @patch('controller.call_llm')
    @patch('controller.execute_tool')
    def test_run_task_no_tools_skips_loop(self, mock_execute, mock_call_llm, controller):
        """If no tool commands in response, ReAct loop should not execute"""
        mock_call_llm.return_value = "I can help with that."

        controller.run_task("Hello")

        mock_execute.assert_not_called()

    @patch('controller.call_llm')
    @patch('controller.execute_tool')
    def test_run_task_single_tool_call(self, mock_execute, mock_call_llm, controller):
        """Tool in first response triggers tool execution, then loop continues"""
        mock_execute.return_value = "[SYSTEM OUTPUT: File read successfully]"

        # First call returns tool use, second call returns final response
        mock_call_llm.side_effect = [
            "!READ /path/to/file",
            "File content is ..."
        ]

        controller.run_task("Read the file")

        assert mock_execute.call_count == 1
        assert mock_execute.call_args[0][0] == "!READ"
        assert mock_call_llm.call_count == 2  # Initial + after tool

    @patch('controller.call_llm')
    @patch('controller.execute_tool')
    def test_run_task_strips_leading_trailing_newlines_from_tools(self, mock_execute, mock_call_llm, controller):
        """execute_tool is called with response containing the full text including markers"""
        mock_execute.return_value = "[SYSTEM OUTPUT: done]"

        response_with_newlines = """Here's what I found:

!READ /some/file

That should help."""
        mock_call_llm.side_effect = [response_with_newlines, "Final response"]

        controller.run_task("Find the file")

        # Verify execute_tool received the full response content
        call_args = mock_execute.call_args
        assert call_args is not None

    @patch('controller.call_llm')
    @patch('controller.execute_tool')
    def test_run_task_returns_final_response(self, mock_execute, mock_call_llm, controller):
        """run_task() should return the final response string"""
        mock_call_llm.return_value = "Final answer from Bob"
        mock_execute.return_value = None  # No tools, so loop exits immediately

        result = controller.run_task("What is the answer?")

        assert result == "Final answer from Bob"

    @patch('controller.call_llm')
    @patch('controller.execute_tool')
    def test_run_task_multiple_tools_sequential(self, mock_execute, mock_call_llm, controller):
        """When multiple tools in response, only first is executed (serial mode)"""
        mock_execute.return_value = "[SYSTEM OUTPUT: first tool done]"

        # Response has two tools, but only first should execute
        response_with_two_tools = "!READ /file1.txt\nThen !WRITE /file2.txt"
        mock_call_llm.side_effect = [
            response_with_two_tools,
            "Done with everything"
        ]

        controller.run_task("Read and write files")

        # Only one tool call despite two tools in response
        assert mock_execute.call_count == 1


class TestControllerModuleLevelFunctions:
    """Tests for backward-compatible module-level init() and run_task()"""

    @patch('controller.terminal_history_upgrade')
    @patch('controller.ProviderManager')
    @patch('controller.AGENT_md_INGESTIOR')
    def test_init_creates_global_controller(self, mock_agent, mock_pm_class, mock_terminal):
        """init() should create a global _controller instance"""
        mock_pm_instance = MagicMock()
        mock_pm_class.return_value = mock_pm_instance
        mock_provider = MagicMock()
        mock_pm_instance.get_provider.return_value = mock_provider
        mock_agent.return_value = ""

        import controller
        controller.init()

        assert controller._controller is not None
        assert isinstance(controller._controller, controller.HarnessController)

    @patch('controller.terminal_history_upgrade')
    @patch('controller.ProviderManager')
    @patch('controller.AGENT_md_INGESTIOR')
    def test_run_task_uses_global_controller(self, mock_agent, mock_pm_class, mock_terminal):
        """module run_task() should delegate to global controller"""
        mock_pm_instance = MagicMock()
        mock_pm_class.return_value = mock_pm_instance
        mock_provider = MagicMock()
        mock_pm_instance.get_provider.return_value = mock_provider
        mock_agent.return_value = ""

        with patch('controller.call_llm', return_value="Response") as mock_llm:
            import controller
            controller.init()
            result = controller.run_task("Hello")

            assert result == "Response"
            assert mock_llm.called

    @patch('controller.terminal_history_upgrade')
    @patch('controller.ProviderManager')
    @patch('controller.AGENT_md_INGESTIOR')
    def test_run_task_raises_without_init(self, mock_agent, mock_pm_class, mock_terminal):
        """module run_task() should raise if init() not called"""
        mock_pm_instance = MagicMock()
        mock_pm_class.return_value = mock_pm_instance
        mock_provider = MagicMock()
        mock_pm_instance.get_provider.return_value = mock_provider
        mock_agent.return_value = ""

        import controller
        # Reset to simulate fresh import without init
        controller._controller = None

        with pytest.raises(RuntimeError, match="Controller not initialized"):
            controller.run_task("test")


class TestToolRegexParsing:
    """Tests for the ReAct tool detection regex logic"""

    def test_regex_finds_write_command(self):
        """Regex should detect !WRITE command at start of response"""
        response = "!READ /path/to/file"
        pattern = r'^\s*!(READ)\s+(\S+)'
        match = re.search(pattern, response, re.MULTILINE)
        assert match is not None
        assert match.group(1) == "READ"
        assert match.group(2) == "/path/to/file"

    def test_regex_finds_write_command_indented(self):
        """Regex should detect !WRITE command even when indented"""
        response = "  !WRITE /path/to/file"
        pattern = r'^\s*!(WRITE)\s+(\S+)'
        match = re.search(pattern, response, re.MULTILINE)
        assert match is not None
        assert match.group(1) == "WRITE"

    def test_regex_finds_bash_command(self):
        """Regex should detect !BASH command"""
        response = "!BASH ls -la /tmp"
        pattern = r'^\s*!(BASH)\s+(.+)'
        match = re.search(pattern, response, re.MULTILINE)
        assert match is not None
        assert match.group(1) == "BASH"
        assert match.group(2) == "ls -la /tmp"

    def test_regex_finds_ls_command(self):
        """Regex should detect !LS command"""
        response = "!LS /home/user"
        pattern = r'^\s*!(LS)\s+(\S+)'
        match = re.search(pattern, response, re.MULTILINE)
        assert match is not None
        assert match.group(1) == "LS"

    def test_first_match_selected_when_multiple(self):
        """When multiple tools detected, first one in text should be selected"""
        response = "!READ /file1.txt\n\nThen !WRITE /file2.txt"
        regex_map = {
            "!WRITE": r'^\s*!(WRITE)\s+(\S+)',
            "!READ": r'^\s*!(READ)\s+(\S+)',
        }

        matches = []
        for cmd_type, pattern in regex_map.items():
            m = re.search(pattern, response, re.MULTILINE)
            if m:
                matches.append((m.start(), cmd_type, m))

        matches.sort(key=lambda x: x[0])
        _, tool_cmd, match = matches[0]

        assert tool_cmd == "!READ"
        assert match.group(2) == "/file1.txt"


class TestExecuteNextTool:
    """Tests for HarnessController._execute_next_tool()"""

    @pytest.fixture
    def controller(self):
        with patch('controller.terminal_history_upgrade'), \
             patch('controller.ProviderManager') as mock_pm_class, \
             patch('controller.AGENT_md_INGESTIOR', return_value=""):
            mock_pm_instance = MagicMock()
            mock_pm_class.return_value = mock_pm_instance
            mock_provider = MagicMock()
            mock_pm_instance.get_provider.return_value = mock_provider

            from controller import HarnessController
            ctrl = HarnessController(enable_context=False)
            return ctrl

    def test_execute_next_tool_returns_none_when_no_match(self, controller):
        """_execute_next_tool returns (None, None) if no tool command found"""
        result, file_path = controller._execute_next_tool("Just a plain response")
        assert result is None
        assert file_path is None

    @patch('controller.execute_tool')
    def test_execute_next_tool_executes_first_match(self, mock_execute, controller):
        """_execute_next_tool executes the first tool found in text order"""
        mock_execute.return_value = "[SYSTEM OUTPUT: done]"

        response = "!READ /path/to/file\n!WRITE /another/file"
        result, file_path = controller._execute_next_tool(response)

        # Only !READ should be executed (first in text)
        # !READ only passes command + path (no content), unlike !WRITE/!EDIT
        mock_execute.assert_called_once_with("!READ", "/path/to/file")
        assert result == "[SYSTEM OUTPUT: done]"
        # !READ doesn't return file_path (only WRITE/EDIT do)
        assert file_path is None

    @patch('controller.execute_tool')
    def test_execute_next_tool_passes_content_for_write_edit(self, mock_execute, controller):
        """_execute_next_tool passes full response for WRITE/EDIT to parse markers"""
        mock_execute.return_value = "[SYSTEM OUTPUT: done]"

        response = "!WRITE /file.txt\n<<<WRITE_BLOCK>>>content<<<"
        result, file_path = controller._execute_next_tool(response)

        # Verify full response passed for marker parsing
        _, _, content = mock_execute.call_args[0]
        assert "<<<WRITE_BLOCK>>>" in content
        assert file_path == "/file.txt"

    @patch('controller.execute_tool')
    def test_execute_next_tool_no_content_param_for_read(self, mock_execute, controller):
        """_execute_next_tool passes only path for non-WRITE/EDIT commands"""
        mock_execute.return_value = "[SYSTEM OUTPUT: done]"

        response = "!READ /path/to/file"
        result, file_path = controller._execute_next_tool(response)

        # Should be called with just command and path (no content)
        mock_execute.assert_called_once_with("!READ", "/path/to/file")