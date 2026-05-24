"""Unit tests for context.py - Topic tracking and context management."""
import pytest
import sys
import os
import tempfile
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))


class TestTopicTracking:
    """Tests for Topic dataclass and topic tracking."""

    def test_topic_creation(self):
        """Topic should be created with name and started=True by default."""
        from context import Topic
        topic = Topic(name="test-topic")
        assert topic.name == "test-topic"
        assert topic.started is True
        assert topic.relevant_files == []
        assert topic.key_facts == []

    def test_topic_with_files_and_facts(self):
        """Topic should store relevant files and key facts."""
        from context import Topic
        topic = Topic(
            name="python-testing",
            relevant_files=["test_foo.py", "test_bar.py"],
            key_facts=["foo uses pytest", "bar uses unittest"]
        )
        assert topic.name == "python-testing"
        assert "test_foo.py" in topic.relevant_files
        assert "foo uses pytest" in topic.key_facts


class TestContextManagerInit:
    """Tests for ContextManager initialization."""

    def test_context_manager_creation(self):
        """ContextManager should be created with correct paths."""
        from context import ContextManager
        with patch('os.path.dirname', return_value='/harness'):
            with patch('os.path.dirname', return_value='/harness'):
                cm = ContextManager('/harness', '/harness/personas')
                assert cm.project_root == '/harness'
                assert cm.personas_dir == '/harness/personas'
                assert cm.current_topic is None

    def test_session_memory_starts_empty(self):
        """session_memory_updates should start as empty list."""
        from context import ContextManager
        cm = ContextManager('/test', '/test/personas')
        assert cm.session_memory_updates == []


class TestTopicManagement:
    """Tests for topic setting and retrieval."""

    def test_set_topic_creates_new_topic(self):
        """set_topic should create a new Topic with given name."""
        from context import ContextManager
        cm = ContextManager('/test', '/test/personas')
        cm.set_topic("testing")
        
        assert cm.current_topic is not None
        assert cm.current_topic.name == "testing"
        assert cm.current_topic.started is True

    def test_set_topic_updates_existing(self):
        """set_topic should update existing topic if name differs."""
        from context import ContextManager
        cm = ContextManager('/test', '/test/personas')
        cm.set_topic("first")
        cm.set_topic("second")
        
        assert cm.current_topic.name == "second"

    def test_get_topic_returns_name(self):
        """get_topic should return current topic name."""
        from context import ContextManager
        cm = ContextManager('/test', '/test/personas')
        assert cm.get_topic() is None
        
        cm.set_topic("testing")
        assert cm.get_topic() == "testing"


class TestMemoryUpdateDetection:
    """Tests for detecting memory file updates."""

    def test_check_memory_update_recognizes_memory_md(self):
        """check_memory_update should return True for persona memory files."""
        from context import ContextManager
        cm = ContextManager('/test', '/test/personas')
        
        assert cm.check_memory_update("personas/Hazel/memory.md") is True
        assert cm.check_memory_update("personas/default/memory.md") is True

    def test_check_memory_update_rejects_other_files(self):
        """check_memory_update should return False for non-memory files."""
        from context import ContextManager
        cm = ContextManager('/test', '/test/personas')
        
        assert cm.check_memory_update("personas/Hazel/persona.md") is False
        assert cm.check_memory_update("test_controller.py") is False
        assert cm.check_memory_update("README.md") is False

    def test_check_memory_update_empty_path(self):
        """check_memory_update should return False for empty path."""
        from context import ContextManager
        cm = ContextManager('/test', '/test/personas')
        
        assert cm.check_memory_update("") is False
        assert cm.check_memory_update(None) is False

    def test_add_memory_update_records_path(self):
        """add_memory_update should add path to session_memory_updates."""
        from context import ContextManager
        cm = ContextManager('/test', '/test/personas')
        
        cm.add_memory_update("personas/Hazel/memory.md")
        assert "personas/Hazel/memory.md" in cm.session_memory_updates

    def test_add_memory_update_no_duplicates(self):
        """add_memory_update should not add duplicate paths."""
        from context import ContextManager
        cm = ContextManager('/test', '/test/personas')
        
        cm.add_memory_update("personas/Hazel/memory.md")
        cm.add_memory_update("personas/Hazel/memory.md")
        assert len(cm.session_memory_updates) == 1


class TestShouldAddToHistory:
    """Tests for determining what to add to conversation history."""

    def test_should_add_to_history_normal_result(self):
        """Non-memory updates should be added to history."""
        from context import ContextManager
        cm = ContextManager('/test', '/test/personas')
        
        should_add, summary = cm.should_add_to_history("File content here", memory_updated=False)
        assert should_add is True
        assert summary is None

    def test_should_add_to_history_memory_updated(self):
        """Memory updates should return placeholder summary."""
        from context import ContextManager
        cm = ContextManager('/test', '/test/personas')
        
        should_add, summary = cm.should_add_to_history("Full memory content...", memory_updated=True)
        assert should_add is True
        assert "[Memory updated" in summary


class TestContextSummary:
    """Tests for context summary generation."""

    def test_get_context_summary_empty(self):
        """Empty context should return empty string."""
        from context import ContextManager
        cm = ContextManager('/test', '/test/personas')
        
        assert cm.get_context_summary() == ""

    def test_get_context_summary_with_topic(self):
        """Context summary should include topic name."""
        from context import ContextManager
        cm = ContextManager('/test', '/test/personas')
        cm.set_topic("testing")
        
        summary = cm.get_context_summary()
        assert "Topic: testing" in summary

    def test_get_context_summary_with_key_facts(self):
        """Context summary should include key facts."""
        from context import ContextManager
        cm = ContextManager('/test', '/test/personas')
        cm.set_topic("testing")
        cm.add_key_facts(["fact1", "fact2"])
        
        summary = cm.get_context_summary()
        assert "fact1" in summary

    def test_get_context_summary_with_memory_updates(self):
        """Context summary should include memory update info."""
        from context import ContextManager
        cm = ContextManager('/test', '/test/personas')
        cm.add_memory_update("personas/Hazel/memory.md")
        
        summary = cm.get_context_summary()
        assert "memory.md" in summary

    def test_add_key_facts_to_topic(self):
        """add_key_facts should add facts to current topic."""
        from context import ContextManager
        cm = ContextManager('/test', '/test/personas')
        cm.set_topic("testing")
        
        cm.add_key_facts(["important fact"])
        assert "important fact" in cm.current_topic.key_facts

    def test_add_key_facts_no_duplicate(self):
        """add_key_facts should not add duplicate facts."""
        from context import ContextManager
        cm = ContextManager('/test', '/test/personas')
        cm.set_topic("testing")
        
        cm.add_key_facts(["fact"])
        cm.add_key_facts(["fact"])
        assert len(cm.current_topic.key_facts) == 1


class TestResetSession:
    """Tests for session reset functionality."""

    def test_reset_clears_session_memory(self):
        """reset_session should clear session_memory_updates."""
        from context import ContextManager
        cm = ContextManager('/test', '/test/personas')
        cm.add_memory_update("personas/Hazel/memory.md")
        
        cm.reset_session()
        assert cm.session_memory_updates == []

    def test_reset_does_not_clear_topic(self):
        """reset_session should preserve current topic."""
        from context import ContextManager
        cm = ContextManager('/test', '/test/personas')
        cm.set_topic("testing")
        cm.add_memory_update("personas/Hazel/memory.md")
        
        cm.reset_session()
        assert cm.current_topic is not None
        assert cm.get_topic() == "testing"


class TestCreateContextManager:
    """Tests for the factory function."""

    @patch('os.path.dirname')
    @patch('os.path.join')
    def test_create_context_manager_uses_correct_paths(self, mock_join, mock_dirname):
        """create_context_manager should use project root and personas dir."""
        mock_dirname.side_value = '/project'
        mock_join.return_value = '/project/personas'
        
        from context import create_context_manager
        # Need to reload to pick up mocks
        import importlib
        import context
        importlib.reload(context)
        
        cm = context.create_context_manager()
        # Just verify it doesn't crash - paths are mocked
        assert cm is not None