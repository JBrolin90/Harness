"""Test case for model echo bug: <tool_response>...</tool_response> parsed as tool call.

When local-coder (qwen) model echoes back tool calls in <tool_response> format,
this should NOT be executed as a tool call - it's just the model echoing.

Run with: python3 -m pytest tests/test_model_echo_bug.py -v
"""
import pytest
import sys
import os
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(__file__))

from tool_dispatch import dispatch_with_text_parsing
from llm.response import LLMResponse, ToolResult, SystemError, NoToolFound


class TestModelEchoBug:
    """Test that model echoes in <tool_response> format are NOT executed as tools."""

    def test_tool_response_echo_should_not_be_executed(self):
        """Model output '<tool_response>...</tool_response>' should return NoToolFound.
        
        When the model echoes back a tool call in <tool_response>...</tool_response> format,
        this is just the model echoing what it did, NOT a request to execute that tool.
        """
        text = '<tool_response>Observation: [SYSTEM OUTPUT: Files in /home/joachim/lab/prj/Harness]</tool_response>'
        response = LLMResponse(text=text)
        
        result = dispatch_with_text_parsing(response)
        
        # Should return NoToolFound, NOT try to execute tool_response
        assert isinstance(result, NoToolFound), \
            f"Expected NoToolFound, got {type(result).__name__} - tool_response was incorrectly executed"

    def test_tool_request_echo_should_not_be_executed(self):
        """Model output '<tool_request>...</tool_request>' should return NoToolFound.
        
        Bug: Currently `<tool_request>{"name": "list_files", ...}</tool_request>` is being
        parsed and the JSON inside is extracted and executed as list_files tool.
        This is wrong - the model is just echoing what it did.
        """
        text = '<tool_request>{"name": "list_files", "arguments": {"path": "."}}</tool_request>'
        response = LLMResponse(text=text)
        
        result = dispatch_with_text_parsing(response)
        
        # Should return NoToolFound, NOT execute list_files
        # The model is echoing its tool call, not requesting execution
        assert isinstance(result, NoToolFound), \
            f"Expected NoToolFound, got {type(result).__name__} - tool_request was incorrectly executed"

    def test_real_tool_call_still_works(self):
        """Real tool calls in JSON format should still be parsed and executed.
        
        Uses absolute path and mocks os.getcwd to avoid test isolation issues.
        """
        with patch('tools.base_tool.os.getcwd', return_value='/home/joachim/lab/prj/Harness'):
            text = '{"name": "list_files", "arguments": {"path": "/home/joachim/lab/prj/Harness"}}'
            response = LLMResponse(text=text)
            
            result = dispatch_with_text_parsing(response)
            
            # Should execute list_files
            assert isinstance(result, ToolResult), \
                f"Expected ToolResult, got {type(result).__name__}: {getattr(result, 'message', 'no message')}"
            assert result.tool_name == "list_files", \
                f"Expected 'list_files', got '{result.tool_name}'"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])