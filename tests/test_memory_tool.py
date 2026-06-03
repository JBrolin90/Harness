"""Unit tests for memory_tool.py - Memory management tools."""
import pytest
import sys
import os
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))

from memory import Memory
from tools.memory_tool import MemoryTool, MemoryReadTool


@pytest.fixture
def temp_memory():
    """Create a temporary memory file for testing."""
    with TemporaryDirectory() as tmpdir:
        memory_path = os.path.join(tmpdir, "memory.md")
        # Write empty memory file
        Path(memory_path).write_text("# Memory\n")
        yield memory_path


@pytest.fixture
def memory_with_content():
    """Create a temporary memory file with some content."""
    with TemporaryDirectory() as tmpdir:
        memory_path = os.path.join(tmpdir, "memory.md")
        Path(memory_path).write_text("""# Memory
## Personal
- User prefers Python
- Works on Linux

## Process
- Uses TDD

## Preferences
- Theme: dark

""")
        yield memory_path


class TestMemoryTool:
    """Tests for MemoryTool (add, update, delete actions)."""

    def test_add_new_item(self, temp_memory):
        """Adding a new item to a section works."""
        tool = MemoryTool()
        
        with patch('tools.memory_tool.get_memory') as mock_get:
            mock_get.return_value = Memory(temp_memory)
            result = tool.execute(action="add", section="Personal", item="Likes coffee")
        
        assert "[OK]" in result
        memory = Memory(temp_memory)
        assert "Likes coffee" in memory.get("Personal")

    def test_add_duplicate_item(self, memory_with_content):
        """Adding a duplicate item is ignored."""
        tool = MemoryTool()
        
        with patch('tools.memory_tool.get_memory') as mock_get:
            mock_get.return_value = Memory(memory_with_content)
            initial_count = len(Memory(memory_with_content).get("Personal"))
            result = tool.execute(action="add", section="Personal", item="User prefers Python")
            final_count = len(Memory(memory_with_content).get("Personal"))
        
        assert final_count == initial_count

    def test_update_existing_item(self, memory_with_content):
        """Updating an existing item works."""
        tool = MemoryTool()
        
        with patch('tools.memory_tool.get_memory') as mock_get:
            mock_get.return_value = Memory(memory_with_content)
            result = tool.execute(
                action="update", 
                section="Personal", 
                item="User prefers Python 3", 
                old_item="User prefers Python"
            )
        
        assert "[OK]" in result
        memory = Memory(memory_with_content)
        assert "User prefers Python 3" in memory.get("Personal")
        assert "User prefers Python" not in memory.get("Personal")

    def test_update_nonexistent_item(self, memory_with_content):
        """Updating a nonexistent item returns error."""
        tool = MemoryTool()
        
        with patch('tools.memory_tool.get_memory') as mock_get:
            mock_get.return_value = Memory(memory_with_content)
            result = tool.execute(
                action="update", 
                section="Personal", 
                item="New item", 
                old_item="Does not exist"
            )
        
        assert "[ERROR]" in result

    def test_update_without_old_item(self, memory_with_content):
        """Update without old_item returns error."""
        tool = MemoryTool()
        
        with patch('tools.memory_tool.get_memory') as mock_get:
            mock_get.return_value = Memory(memory_with_content)
            result = tool.execute(action="update", section="Personal", item="New item")
        
        assert "[ERROR]" in result
        assert "old_item" in result

    def test_delete_existing_item(self, memory_with_content):
        """Deleting an existing item works."""
        tool = MemoryTool()
        
        with patch('tools.memory_tool.get_memory') as mock_get:
            mock_get.return_value = Memory(memory_with_content)
            result = tool.execute(action="delete", section="Personal", item="", old_item="User prefers Python")
        
        assert "[OK]" in result
        memory = Memory(memory_with_content)
        assert "User prefers Python" not in memory.get("Personal")

    def test_delete_nonexistent_item(self, memory_with_content):
        """Deleting a nonexistent item returns error."""
        tool = MemoryTool()
        
        with patch('tools.memory_tool.get_memory') as mock_get:
            mock_get.return_value = Memory(memory_with_content)
            result = tool.execute(action="delete", section="Personal", item="", old_item="Does not exist")
        
        assert "[ERROR]" in result

    def test_delete_without_old_item(self, memory_with_content):
        """Delete without old_item returns error."""
        tool = MemoryTool()
        
        with patch('tools.memory_tool.get_memory') as mock_get:
            mock_get.return_value = Memory(memory_with_content)
            result = tool.execute(action="delete", section="Personal", item="")
        
        assert "[ERROR]" in result

    def test_invalid_section(self, temp_memory):
        """Using an invalid section returns error."""
        tool = MemoryTool()
        
        with patch('tools.memory_tool.get_memory') as mock_get:
            mock_get.return_value = Memory(temp_memory)
            result = tool.execute(action="add", section="InvalidSection", item="Test")
        
        assert "[ERROR]" in result
        assert "Invalid section" in result

    def test_invalid_action(self, temp_memory):
        """Using an invalid action returns error."""
        tool = MemoryTool()
        
        with patch('tools.memory_tool.get_memory') as mock_get:
            mock_get.return_value = Memory(temp_memory)
            result = tool.execute(action="invalid", section="Personal", item="Test")
        
        assert "[ERROR]" in result
        assert "Unknown action" in result


class TestMemoryReadTool:
    """Tests for MemoryReadTool."""

    def test_read_empty_memory(self, temp_memory):
        """Reading empty memory returns empty message."""
        tool = MemoryReadTool()
        
        with patch('tools.memory_tool.get_memory') as mock_get:
            mock_get.return_value = Memory(temp_memory)
            result = tool.execute()
        
        assert "[EMPTY]" in result

    def test_read_memory_with_content(self, memory_with_content):
        """Reading memory with content returns all sections."""
        tool = MemoryReadTool()
        
        with patch('tools.memory_tool.get_memory') as mock_get:
            mock_get.return_value = Memory(memory_with_content)
            result = tool.execute()
        
        assert "=== CURRENT MEMORY ===" in result
        assert "## Personal" in result
        assert "User prefers Python" in result
        assert "## Process" in result
        assert "Uses TDD" in result

    def test_read_skips_empty_sections(self, memory_with_content):
        """Reading memory skips sections with no content."""
        tool = MemoryReadTool()
        
        with patch('tools.memory_tool.get_memory') as mock_get:
            mock_get.return_value = Memory(memory_with_content)
            result = tool.execute()
        
        # Voice section is empty in memory_with_content, should not appear
        assert "## Voice" not in result


class TestMemoryToolSchema:
    """Tests for tool schema/integration."""

    def test_memory_tool_registered(self):
        """MemoryTool is properly registered."""
        from tools import BaseTool
        instructions = BaseTool.get_all_instructions()
        tool_names = [t["name"] for t in instructions]
        assert "memory" in tool_names

    def test_memory_read_tool_registered(self):
        """MemoryReadTool is properly registered."""
        from tools import BaseTool
        instructions = BaseTool.get_all_instructions()
        tool_names = [t["name"] for t in instructions]
        assert "memory_read" in tool_names

    def test_memory_tool_parameters(self):
        """MemoryTool has correct parameters schema."""
        tool = MemoryTool()
        assert "action" in tool.parameters["properties"]
        assert "section" in tool.parameters["properties"]
        assert "item" in tool.parameters["properties"]
        assert "old_item" in tool.parameters["properties"]
        assert tool.parameters["properties"]["action"]["enum"] == ["add", "update", "delete"]
