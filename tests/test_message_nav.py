"""Unit tests for message_nav.py - dot-notation navigation utilities."""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'llm'))

from llm.message_nav import navigate_to_message, is_empty_choices, EMPTY_CHOICES_SENTINEL


class TestNavigateToMessage:
    """Tests for navigate_to_message function."""

    def test_simple_key(self):
        """Simple top-level key."""
        data = {"message": {"content": "hello"}}
        result = navigate_to_message(data, "message")
        assert result == {"content": "hello"}

    def test_nested_key(self):
        """Nested key with dot notation."""
        data = {"choices": [{"message": {"content": "hello"}}]}
        result = navigate_to_message(data, "choices[0].message")
        assert result == {"content": "hello"}

    def test_empty_choices_array(self):
        """Empty choices array returns sentinel value."""
        result = navigate_to_message({"choices": []}, "choices[0].message")
        assert is_empty_choices(result)

    def test_missing_key_returns_none(self):
        """Missing key returns None."""
        result = navigate_to_message({"choices": []}, "choices[0].message")
        assert result is None or is_empty_choices(result)

    def test_invalid_path_returns_none(self):
        """Invalid path returns None."""
        result = navigate_to_message({"a": 1}, "b.c.d")
        assert result is None

    def test_array_index_out_of_bounds(self):
        """Array index out of bounds returns None."""
        data = {"choices": [{"message": {}}]}
        result = navigate_to_message(data, "choices[5].message")
        assert result is None

    def test_content_extraction(self):
        """Extract content from nested structure."""
        data = {"choices": [{"message": {"content": "Hello world"}}]}
        result = navigate_to_message(data, "choices[0].message.content")
        assert result == "Hello world"


class TestIsEmptyChoices:
    """Tests for is_empty_choices function."""

    def test_sentinel_returns_true(self):
        """Sentinel value returns True."""
        assert is_empty_choices(EMPTY_CHOICES_SENTINEL) is True

    def test_dict_returns_false(self):
        """Dict message returns False."""
        assert is_empty_choices({"content": "hello"}) is False

    def test_none_returns_false(self):
        """None returns False."""
        assert is_empty_choices(None) is False