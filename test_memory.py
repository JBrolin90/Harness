"""Unit tests for memory.py - Long-term memory management."""
import pytest
import sys
import os
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, os.path.dirname(__file__))

from memory import Memory, load_memory_instructions, get_memory


SECTIONS = Memory.SECTIONS  # Default sections


class TestMemoryInit:
    """Tests for Memory class initialization and file operations."""

    def test_new_memory_empty(self):
        """New Memory instance with no file is empty."""
        with TemporaryDirectory() as tmpdir:
            memory = Memory(os.path.join(tmpdir, "memory.md"))
            assert memory.has_content() is False
            assert memory.get_all() == {section: [] for section in SECTIONS}

    def test_load_existing_memory(self):
        """Memory loads existing file content."""
        with TemporaryDirectory() as tmpdir:
            memory_path = os.path.join(tmpdir, "memory.md")
            Path(memory_path).write_text("""# Memory
## Personal
- User prefers Python
- Works on Linux

## Preferences
- Theme: dark

""")
            memory = Memory(memory_path)
            assert memory.get("Personal") == ["User prefers Python", "Works on Linux"]
            assert memory.get("Preferences") == ["Theme: dark"]

    def test_unknown_sections_are_tracked(self):
        """Unknown sections are dynamically added for tracking."""
        with TemporaryDirectory() as tmpdir:
            memory_path = os.path.join(tmpdir, "memory.md")
            Path(memory_path).write_text("""# Memory
## Personal
- Test item

## Unknown Section
- Tracked dynamically

""")
            memory = Memory(memory_path)
            assert memory.get("Personal") == ["Test item"]
            # Unknown sections are still tracked (not lost)
            assert memory.get("Unknown Section") == ["Tracked dynamically"]


class TestMemoryAdd:
    """Tests for adding items to memory."""

    def test_add_to_existing_section(self):
        """Add item to existing section."""
        with TemporaryDirectory() as tmpdir:
            memory_path = os.path.join(tmpdir, "memory.md")
            Path(memory_path).write_text("""# Memory
## Personal
- Existing item

""")
            memory = Memory(memory_path)
            memory.add("Personal", "New item")
            
            assert "New item" in memory.get("Personal")
            assert "Existing item" in memory.get("Personal")

    def test_add_to_new_section(self):
        """Add item to section that doesn't exist yet."""
        with TemporaryDirectory() as tmpdir:
            memory_path = os.path.join(tmpdir, "memory.md")
            memory = Memory(memory_path)
            memory.add("Custom Section", "Custom item")
            
            assert memory.get("Custom Section") == ["Custom item"]

    def test_add_duplicate_prevented(self):
        """Adding duplicate item is prevented."""
        with TemporaryDirectory() as tmpdir:
            memory_path = os.path.join(tmpdir, "memory.md")
            memory = Memory(memory_path)
            memory.add("Personal", "Test item")
            memory.add("Personal", "Test item")
            
            assert memory.get("Personal").count("Test item") == 1


class TestMemoryUpdate:
    """Tests for updating items in memory."""

    def test_update_existing_item(self):
        """Update an existing item."""
        with TemporaryDirectory() as tmpdir:
            memory_path = os.path.join(tmpdir, "memory.md")
            Path(memory_path).write_text("""# Memory
## Preferences
- Theme: light

""")
            memory = Memory(memory_path)
            result = memory.update("Preferences", "Theme: light", "Theme: dark")
            
            assert result is True
            assert "Theme: dark" in memory.get("Preferences")
            assert "Theme: light" not in memory.get("Preferences")

    def test_update_nonexistent_item(self):
        """Update returns False for non-existent item."""
        with TemporaryDirectory() as tmpdir:
            memory_path = os.path.join(tmpdir, "memory.md")
            memory = Memory(memory_path)
            result = memory.update("Personal", "Non-existent", "New value")
            
            assert result is False

    def test_update_nonexistent_section(self):
        """Update returns False for non-existent section."""
        with TemporaryDirectory() as tmpdir:
            memory_path = os.path.join(tmpdir, "memory.md")
            memory = Memory(memory_path)
            result = memory.update("Ghost Section", "item", "value")
            
            assert result is False


class TestMemoryRemove:
    """Tests for removing items from memory."""

    def test_remove_existing_item(self):
        """Remove an existing item."""
        with TemporaryDirectory() as tmpdir:
            memory_path = os.path.join(tmpdir, "memory.md")
            Path(memory_path).write_text("""# Memory
## Personal
- Item to remove
- Item to keep

""")
            memory = Memory(memory_path)
            result = memory.remove("Personal", "Item to remove")
            
            assert result is True
            assert "Item to remove" not in memory.get("Personal")
            assert "Item to keep" in memory.get("Personal")

    def test_remove_nonexistent_item(self):
        """Remove returns False for non-existent item."""
        with TemporaryDirectory() as tmpdir:
            memory_path = os.path.join(tmpdir, "memory.md")
            memory = Memory(memory_path)
            result = memory.remove("Personal", "Ghost item")
            
            assert result is False


class TestMemoryFind:
    """Tests for searching memory."""

    def test_find_in_section(self):
        """Find items containing query."""
        with TemporaryDirectory() as tmpdir:
            memory_path = os.path.join(tmpdir, "memory.md")
            Path(memory_path).write_text("""# Memory
## Personal
- User works with Python
- User works with Rust

## Preferences
- Uses dark theme

""")
            memory = Memory(memory_path)
            results = memory.find("Python")
            
            assert len(results) == 1
            assert results[0] == ("Personal", "User works with Python")

    def test_find_case_insensitive(self):
        """Search is case-insensitive."""
        with TemporaryDirectory() as tmpdir:
            memory_path = os.path.join(tmpdir, "memory.md")
            memory = Memory(memory_path)
            memory.add("Personal", "Works with PYTHON")
            
            results = memory.find("python")
            assert len(results) == 1

    def test_find_multiple_matches(self):
        """Find returns all matching items."""
        with TemporaryDirectory() as tmpdir:
            memory_path = os.path.join(tmpdir, "memory.md")
            memory = Memory(memory_path)
            memory.add("Personal", "Uses VSCode")
            memory.add("Personal", "Uses VIM")
            memory.add("Preferences", "Prefers VSCode")
            
            results = memory.find("VSCode")
            assert len(results) == 2


class TestMemoryClearSection:
    """Tests for clearing sections."""

    def test_clear_section_with_content(self):
        """Clear section with existing content."""
        with TemporaryDirectory() as tmpdir:
            memory_path = os.path.join(tmpdir, "memory.md")
            Path(memory_path).write_text("""# Memory
## Preferences
- Theme: dark
- Font: monospace

""")
            memory = Memory(memory_path)
            result = memory.clear_section("Preferences")
            
            assert result is True
            assert memory.get("Preferences") == []

    def test_clear_nonexistent_section(self):
        """Clear returns False for non-existent section."""
        with TemporaryDirectory() as tmpdir:
            memory_path = os.path.join(tmpdir, "memory.md")
            memory = Memory(memory_path)
            result = memory.clear_section("Ghost Section")
            
            assert result is False


class TestMemoryPersistence:
    """Tests for file persistence."""

    def test_add_persists_to_file(self):
        """Adding item saves to file."""
        with TemporaryDirectory() as tmpdir:
            memory_path = os.path.join(tmpdir, "memory.md")
            memory = Memory(memory_path)
            memory.add("Personal", "New preference")
            
            # Reload and check
            memory2 = Memory(memory_path)
            assert "New preference" in memory2.get("Personal")

    def test_update_persists_to_file(self):
        """Updating item saves to file."""
        with TemporaryDirectory() as tmpdir:
            memory_path = os.path.join(tmpdir, "memory.md")
            memory = Memory(memory_path)
            memory.add("Preferences", "old value")
            memory.update("Preferences", "old value", "new value")
            
            memory2 = Memory(memory_path)
            assert "new value" in memory2.get("Preferences")
            assert "old value" not in memory2.get("Preferences")

    def test_remove_persists_to_file(self):
        """Removing item saves to file."""
        with TemporaryDirectory() as tmpdir:
            memory_path = os.path.join(tmpdir, "memory.md")
            memory = Memory(memory_path)
            memory.add("Personal", "To remove")
            memory.remove("Personal", "To remove")
            
            memory2 = Memory(memory_path)
            assert "To remove" not in memory2.get("Personal")

    def test_empty_sections_not_saved(self):
        """Empty sections are not written to file."""
        with TemporaryDirectory() as tmpdir:
            memory_path = os.path.join(tmpdir, "memory.md")
            memory = Memory(memory_path)
            memory.add("Personal", "Has content")
            
            content = Path(memory_path).read_text()
            assert "## Preferences" not in content
            assert "## Knowledge Base" not in content


class TestLoadMemoryInstructions:
    """Tests for loading memory instructions."""

    def test_load_existing_instructions(self):
        """Load existing instructions file."""
        with TemporaryDirectory() as tmpdir:
            instructions_path = os.path.join(tmpdir, "memory_instructions.md")
            Path(instructions_path).write_text("# Memory Instructions\n\nTest content.")
            
            content = load_memory_instructions(instructions_path)
            assert content == "# Memory Instructions\n\nTest content."

    def test_load_nonexistent_instructions(self):
        """Load returns None for non-existent file."""
        with TemporaryDirectory() as tmpdir:
            content = load_memory_instructions(os.path.join(tmpdir, "ghost.md"))
            assert content is None


class TestModuleFunctions:
    """Tests for module-level convenience functions."""

    def test_get_memory_creates_instance(self):
        """get_memory returns Memory instance."""
        with TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            memory = get_memory()
            assert isinstance(memory, Memory)

    def test_get_memory_with_path(self):
        """get_memory accepts path argument."""
        with TemporaryDirectory() as tmpdir:
            memory_path = os.path.join(tmpdir, "custom.md")
            memory = get_memory(memory_path)
            assert memory.memory_path == Path(memory_path)


class TestGetAll:
    """Tests for get_all method."""

    def test_get_all_returns_copy(self):
        """get_all returns a copy, not the internal dict."""
        with TemporaryDirectory() as tmpdir:
            memory_path = os.path.join(tmpdir, "memory.md")
            memory = Memory(memory_path)
            memory.add("Personal", "Test item")
            
            result = memory.get_all()
            result["Personal"].append("Modified")
            
            assert memory.get("Personal") == ["Test item"]

    def test_get_all_includes_all_sections(self):
        """get_all includes all defined sections."""
        with TemporaryDirectory() as tmpdir:
            memory_path = os.path.join(tmpdir, "memory.md")
            memory = Memory(memory_path)
            
            result = memory.get_all()
            for section in SECTIONS:
                assert section in result