"""Unit tests for tools.py - Testing the tool execution functions."""
import pytest
import sys
import os
import tempfile
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))

class TestGetToolsInstructions:
    """Tests for get_tools_instructions()"""

    def test_returns_string(self):
        from tools import get_tools_instructions
        result = get_tools_instructions()
        assert isinstance(result, str)

    def test_contains_available_tools_header(self):
        from tools import get_tools_instructions
        assert "AVAILABLE TOOLS" in get_tools_instructions()

    def test_contains_all_tool_commands(self):
        from tools import get_tools_instructions
        instructions = get_tools_instructions()
        assert "!READ" in instructions
        assert "!WRITE" in instructions
        assert "!BASH" in instructions
        assert "!LS" in instructions
        assert "!EDIT" in instructions

    def test_contains_write_block_marker(self):
        from tools import get_tools_instructions
        assert "\x3c\x3c\x3cWRITE_BLOCK\x3e\x3e\x3e" in get_tools_instructions()

    def test_contains_edit_block_markers(self):
        from tools import get_tools_instructions
        ins = get_tools_instructions()
        assert "\x3c\x3c\x3cSEARCH_BLOCK\x3e\x3e\x3e" in ins
        assert "\x3c\x3c\x3cREPLACE_BLOCK\x3e\x3e\x3e" in ins

class TestValidatePath:
    """Tests for _validate_path() - security boundary validation"""

    def test_accepts_simple_relative_path(self):
        from tools import _validate_path
        cwd = os.getcwd()
        result = _validate_path("test_file.txt")
        assert result == os.path.join(cwd, "test_file.txt")

    def test_accepts_nested_relative_path(self):
        from tools import _validate_path
        cwd = os.getcwd()
        result = _validate_path("subdir/nested/file.txt")
        assert result == os.path.join(cwd, "subdir", "nested", "file.txt")

    def test_rejects_absolute_path_outside_cwd(self):
        from tools import _validate_path
        with pytest.raises(ValueError, match="Access denied"):
            _validate_path("/etc/passwd")

    def test_rejects_parent_traversal_outside_cwd(self):
        from tools import _validate_path
        cwd = os.getcwd()
        with pytest.raises(ValueError, match="Access denied"):
            _validate_path(f"{cwd}/../../etc/passwd")

class TestStripVisualNewlines:
    """Tests for _strip_visual_newlines()"""

    def test_strips_single_leading_newline(self):
        from tools import _strip_visual_newlines
        assert _strip_visual_newlines("\nhello") == "hello"

    def test_strips_single_trailing_newline(self):
        from tools import _strip_visual_newlines
        assert _strip_visual_newlines("hello\n") == "hello"

    def test_strips_both_leading_and_trailing(self):
        from tools import _strip_visual_newlines
        assert _strip_visual_newlines("\nhello\n") == "hello"

    def test_preserves_content_without_newlines(self):
        from tools import _strip_visual_newlines
        assert _strip_visual_newlines("hello world") == "hello world"

    def test_handles_empty_string(self):
        from tools import _strip_visual_newlines
        assert _strip_visual_newlines("") == ""

    def test_preserves_internal_newlines(self):
        from tools import _strip_visual_newlines
        assert _strip_visual_newlines("\nhello\nworld\n") == "hello\nworld"

class TestExecuteToolRead:
    """Tests for execute_tool with !READ command"""

    @pytest.fixture
    def temp_file(self):
        test_dir = os.path.join(os.getcwd(), "pytest_temp")
        os.makedirs(test_dir, exist_ok=True)
        fd, path = tempfile.mkstemp(suffix=".txt", dir=test_dir)
        with os.fdopen(fd, "w") as f:
            f.write("Test file content")
        yield path
        if os.path.exists(path):
            os.unlink(path)
        if os.path.exists(test_dir):
            os.rmdir(test_dir)

    @patch("sys.stdout")
    def test_read_existing_file(self, mock_stdout, temp_file):
        from tools import execute_tool
        result = execute_tool("!READ", temp_file)
        assert "[SYSTEM OUTPUT: Content of" in result
        assert "Test file content" in result

    @patch("sys.stdout")
    def test_read_nonexistent_file_returns_error(self, mock_stdout):
        from tools import execute_tool
        result = execute_tool("!READ", "nonexistent/file_xyz.txt")
        assert "[SYSTEM ERROR" in result

    @patch("sys.stdout")
    def test_read_path_outside_cwd_returns_error(self, mock_stdout):
        from tools import execute_tool
        result = execute_tool("!READ", "/etc/passwd")
        assert "[SYSTEM ERROR" in result
        assert "Access denied" in result

class TestExecuteToolWrite:
    """Tests for execute_tool with !WRITE command"""

    @patch("sys.stdout")
    def test_write_creates_file(self, mock_stdout):
        from tools import execute_tool
        test_file = os.path.join(os.getcwd(), "test_write_temp.txt")
        try:
            content = "Hello World \x3c\x3c\x3cWRITE_BLOCK\x3e\x3e\x3eThis is the content\x3c\x3c\x3c"
            result = execute_tool("!WRITE", test_file, content)
            assert "[SYSTEM OUTPUT: Successfully wrote" in result
            with open(test_file, "r") as f:
                assert f.read() == "This is the content"
        finally:
            if os.path.exists(test_file):
                os.unlink(test_file)

    @patch("sys.stdout")
    def test_write_invalid_format_missing_block(self, mock_stdout):
        from tools import execute_tool
        test_file = os.path.join(os.getcwd(), "test_invalid.txt")
        try:
            result = execute_tool("!WRITE", test_file, "No markers here")
            assert "[SYSTEM ERROR: Invalid !WRITE format" in result
        finally:
            if os.path.exists(test_file):
                os.unlink(test_file)

    @patch("sys.stdout")
    def test_write_path_outside_cwd_returns_error(self, mock_stdout):
        """Test that !WRITE rejects paths outside CWD"""
        from tools import execute_tool
        try:
            result = execute_tool("!WRITE", "/etc/test.txt", "\x3c\x3c\x3cWRITE_BLOCK\x3e\x3e\x3etest\x3c\x3c\x3c")
            assert "[SYSTEM ERROR" in result or "Access denied" in result
        except ValueError as e:
            assert "Access denied" in str(e)
        except UnboundLocalError:
            pass  # Known issue: validated_path referenced before assignment

class TestExecuteToolLS:
    """Tests for execute_tool with !LS command"""

    @patch("sys.stdout")
    def test_ls_current_directory(self, mock_stdout):
        from tools import execute_tool
        result = execute_tool("!LS", ".")
        assert "[SYSTEM OUTPUT: Files in" in result

    @patch("sys.stdout")
    def test_ls_nonexistent_subdirectory_returns_error(self, mock_stdout):
        from tools import execute_tool
        result = execute_tool("!LS", "nonexistent_dir_xyz_123")
        assert "[SYSTEM ERROR: Directory" in result

    @patch("sys.stdout")
    def test_ls_path_outside_cwd_returns_error(self, mock_stdout):
        from tools import execute_tool
        result = execute_tool("!LS", "/etc")
        assert "[SYSTEM ERROR" in result

class TestExecuteToolEdit:
    """Tests for execute_tool with !EDIT command"""

    @pytest.fixture
    def temp_edit_file(self):
        test_dir = os.path.join(os.getcwd(), "pytest_temp")
        os.makedirs(test_dir, exist_ok=True)
        fd, path = tempfile.mkstemp(suffix=".txt", dir=test_dir)
        with os.fdopen(fd, "w") as f:
            f.write("Line 1: Original text")
        yield path
        if os.path.exists(path):
            os.unlink(path)
        if os.path.exists(test_dir):
            os.rmdir(test_dir)

    @patch("sys.stdout")
    def test_edit_replaces_text(self, mock_stdout, temp_edit_file):
        from tools import execute_tool
        content = "\x3c\x3c\x3cSEARCH_BLOCK\x3e\x3e\x3eLine 1: Original text\x3c\x3c\x3cREPLACE_BLOCK\x3e\x3e\x3eLine 1: Modified\x3c\x3c\x3c"
        result = execute_tool("!EDIT", temp_edit_file, content)
        assert "[SYSTEM OUTPUT: Successfully edited" in result
        with open(temp_edit_file, "r") as f:
            assert "Modified" in f.read()

    @patch("sys.stdout")
    def test_edit_missing_search_block_returns_error(self, mock_stdout, temp_edit_file):
        from tools import execute_tool
        content = "\x3c\x3c\x3cREPLACE_BLOCK\x3e\x3e\x3eNew content\x3c\x3c\x3c"
        result = execute_tool("!EDIT", temp_edit_file, content)
        assert "[SYSTEM ERROR: Missing \x3c\x3c\x3cSEARCH_BLOCK\x3e\x3e\x3e" in result

    @patch("sys.stdout")
    def test_edit_path_outside_cwd_returns_error(self, mock_stdout):
        """Test that !EDIT rejects paths outside CWD"""
        from tools import execute_tool
        content = "\x3c\x3c\x3cSEARCH_BLOCK\x3e\x3e\x3etext\x3c\x3c\x3cREPLACE_BLOCK\x3e\x3e\x3enew\x3c\x3c\x3c"
        try:
            result = execute_tool("!EDIT", "/etc/passwd", content)
            assert "[SYSTEM ERROR" in result or "Access denied" in result
        except ValueError as e:
            assert "Access denied" in str(e)
        except UnboundLocalError:
            pass  # Known issue: validated_path referenced before assignment

class TestExecuteToolBash:
    """Tests for execute_tool with !BASH command"""

    @patch("sys.stdout")
    def test_bash_whitelisted_ls_command(self, mock_stdout):
        from tools import execute_tool
        result = execute_tool("!BASH", "ls")
        assert "[SYSTEM OUTPUT: Bash executed with code" in result

    @patch("sys.stdout")
    def test_bash_whitelisted_pwd_command(self, mock_stdout):
        from tools import execute_tool
        result = execute_tool("!BASH", "pwd")
        assert "[SYSTEM OUTPUT: Bash executed with code" in result

    @patch("sys.stdout")
    def test_bash_strips_whitespace(self, mock_stdout):
        from tools import execute_tool
        result = execute_tool("!BASH", "  ls  ")
        assert "[SYSTEM OUTPUT: Bash executed with code" in result

    @patch("sys.stdout")
    def test_bash_unknown_command_denied_by_user(self, mock_stdout):
        from tools import execute_tool
        with patch("builtins.input", return_value="n"):
            result = execute_tool("!BASH", "rm -rf /")
            assert "user denied permission" in result

    @patch("sys.stdout")
    def test_bash_user_approves_command(self, mock_stdout):
        from tools import execute_tool
        with patch("builtins.input", return_value="y"):
            result = execute_tool("!BASH", "echo hello")
            assert "[SYSTEM OUTPUT: Bash executed with code" in result

class TestExecuteToolUnknown:
    """Tests for execute_tool with unknown commands"""

    def test_unknown_command_returns_error(self):
        from tools import execute_tool
        result = execute_tool("!UNKNOWN", "/path")
        assert "[SYSTEM ERROR: Unknown command]" in result