"""Unit tests for systemprompt.py - System prompt builder."""
import pytest
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))


class TestBuildMemorySection:
    """Tests for _build_memory_section function."""

    def test_empty_memory_returns_empty_string(self):
        """Empty memory returns empty string."""
        from systemprompt import _build_memory_section
        mock_memory = MagicMock()
        mock_memory.has_content.return_value = False

        result = _build_memory_section(mock_memory)
        assert result == ""

    def test_none_memory_returns_empty_string(self):
        """None memory returns empty string."""
        from systemprompt import _build_memory_section
        result = _build_memory_section(None)
        assert result == ""

    def test_memory_with_content_returns_section(self):
        """Memory with content returns formatted section."""
        from systemprompt import _build_memory_section
        mock_memory = MagicMock()
        mock_memory.has_content.return_value = True
        mock_memory.get_all.return_value = {
            "Personal": ["User works with Python"],
            "Preferences": []
        }

        result = _build_memory_section(mock_memory)

        assert "LONG-TERM MEMORY:" in result
        assert "## Personal" in result
        assert "User works with Python" in result
        assert "## Preferences" not in result  # Empty section excluded

    def test_multiple_sections_all_rendered(self):
        """All non-empty sections are rendered."""
        from systemprompt import _build_memory_section
        mock_memory = MagicMock()
        mock_memory.has_content.return_value = True
        mock_memory.get_all.return_value = {
            "Personal": ["Item 1", "Item 2"],
            "Process": ["Works on Linux"],
            "Preferences": []
        }

        result = _build_memory_section(mock_memory)

        assert "## Personal" in result
        assert "## Process" in result
        assert "- Item 1" in result
        assert "- Item 2" in result
        assert "- Works on Linux" in result


class TestBuildMemoryInstructions:
    """Tests for _build_memory_instructions function."""

    @patch('memory.load_memory_instructions')
    def test_with_instructions_file(self, mock_load):
        """When instructions file exists, returns formatted content."""
        import systemprompt
        mock_load.return_value = "# Memory Instructions\n\nTest content."

        result = systemprompt._build_memory_instructions()

        assert "MEMORY SYSTEM INSTRUCTIONS" in result
        assert "# Memory Instructions" in result
        assert "Test content." in result

    @patch('memory.load_memory_instructions')
    def test_without_instructions_file(self, mock_load):
        """When no instructions file, returns empty string."""
        import systemprompt
        mock_load.return_value = None

        result = systemprompt._build_memory_instructions()

        assert result == ""


class TestBuildSystemPrompt:
    """Tests for build_system_prompt function."""

    @patch('os.getcwd')
    def test_with_memory_includes_memory_section(self, mock_getcwd):
        """When memory has content, memory section is included."""
        import systemprompt
        mock_getcwd.return_value = "/test/project"

        mock_memory = MagicMock()
        mock_memory.has_content.return_value = True
        mock_memory.get_all.return_value = {
            "Personal": ["User works with Python"],
            "Preferences": []
        }

        with patch.object(systemprompt, '_build_tools_section', return_value="TOOLS: tool1"), \
             patch.object(systemprompt, '_build_system_prompt_additions', return_value=""), \
             patch.object(systemprompt, 'AGENT_md_INGESTIOR', return_value=""):

            result = systemprompt.build_system_prompt(mock_memory)

            assert "LONG-TERM MEMORY:" in result
            assert "## Personal" in result
            assert "User works with Python" in result
            assert "## Preferences" not in result  # Empty section excluded

    @patch('os.getcwd')
    def test_without_memory_excludes_section(self, mock_getcwd):
        """When memory is None, memory section is excluded."""
        import systemprompt
        mock_getcwd.return_value = "/test/project"

        with patch.object(systemprompt, '_build_tools_section', return_value="TOOLS: tool1"), \
             patch.object(systemprompt, '_build_system_prompt_additions', return_value=""), \
             patch.object(systemprompt, 'AGENT_md_INGESTIOR', return_value=""), \
             patch.object(systemprompt, '_build_memory_section', return_value=""):

            result = systemprompt.build_system_prompt(None)

            assert "LONG-TERM MEMORY:" not in result

    @patch('systemprompt.AGENT_md_INGESTIOR')
    @patch('systemprompt._build_memory_section')
    @patch('systemprompt._build_memory_instructions')
    @patch('os.getcwd')
    def test_includes_tools_and_agent_md(
        self, mock_getcwd, mock_mem_instr, mock_mem_section, mock_agent
    ):
        """build_system_prompt always includes tools and AGENT.md."""
        from systemprompt import build_system_prompt
        
        mock_getcwd.return_value = "/test/project"

        with patch('systemprompt._build_tools_section', return_value="AVAILABLE TOOLS:\n- read_file: Read file contents"), \
             patch('systemprompt._build_system_prompt_additions', return_value="Additional instructions"), \
             patch('systemprompt.AGENT_md_INGESTIOR', return_value="=== AGENT.md ===\nCustom instructions\n==="), \
             patch('systemprompt._build_memory_section', return_value=""), \
             patch('systemprompt._build_memory_instructions', return_value=""):

            result = build_system_prompt(None)

            assert "AVAILABLE TOOLS:" in result
            assert "read_file" in result
            assert "AGENT.md" in result
            assert "Additional instructions" in result