"""Debug test to trace how '...' becomes a bash command."""
import sys
sys.path.insert(0, '/home/joachim/lab/prj/Harness')

from tool_dispatch import (
    dispatch,
    parse_bash_command,
    extract_json_string,
    _parse_plain_tool_call,
    _parse_xml_tool_call,
    _parse_colon_json_format,
    _parse_simple_tool_json,
    _parse_json_raw,
)
from llm.response import LLMResponse, ToolCall

# Clear and set up a mock bash tool
from tools.base_tool import BaseTool

class MockBashTool(BaseTool):
    name = "bash"
    description = ""
    parameters = {"type": "object", "properties": {}, "required": []}
    def execute(self, **kw):
        return f"[EXECUTED: bash with {kw}]"

BaseTool._registry["bash"] = MockBashTool


print("=" * 60)
print("TEST 1: Text '...' directly to dispatch")
print("=" * 60)
resp1 = LLMResponse(text="...")
result1 = dispatch(resp1)
print(f"Result type: {type(result1).__name__}")
print(f"Result: {result1}")
print()

print("=" * 60)
print("TEST 2: Text with code fence '```bash\\n...\\n```'")
print("=" * 60)
resp2 = LLMResponse(text="```bash\n...\n```")
result2 = dispatch(resp2)
print(f"Result type: {type(result2).__name__}")
print(f"Result: {result2}")
print()

print("=" * 60)
print("TEST 3: Text with partial code fence '```bash\\n...'")
print("=" * 60)
resp3 = LLMResponse(text="```bash\n...")
result3 = dispatch(resp3)
print(f"Result type: {type(result3).__name__}")
print(f"Result: {result3}")
print()

print("=" * 60)
print("TEST 4: Native tool_call 'bash' with '...' argument")
print("=" * 60)
resp4 = LLMResponse(tool_calls=[ToolCall(name="bash", arguments={"command": "..."})])
result4 = dispatch(resp4)
print(f"Result type: {type(result4).__name__}")
print(f"Result: {result4}")
print()

print("=" * 60)
print("TEST 5: Check each parser individually on '...'")
print("=" * 60)
text = "..."
print(f"parse_bash_command: {parse_bash_command(text)}")
print(f"extract_json_string: {extract_json_string(text)}")
print(f"_parse_json_raw: {_parse_json_raw(text)}")
print(f"_parse_simple_tool_json: {_parse_simple_tool_json(text)}")
print(f"_parse_colon_json_format: {_parse_colon_json_format(text)}")
print(f"_parse_xml_tool_call: {_parse_xml_tool_call(text)}")
print(f"_parse_plain_tool_call: {_parse_plain_tool_call(text)}")
print()

print("=" * 60)
print("TEST 6: Check each parser on '```bash\\n...\\n```'")
print("=" * 60)
text = "```bash\n...\n```"
print(f"parse_bash_command: {parse_bash_command(text)}")
print(f"extract_json_string: {extract_json_string(text)}")
print(f"_parse_json_raw: {_parse_json_raw(text)}")
print(f"_parse_simple_tool_json: {_parse_simple_tool_json(text)}")
print(f"_parse_colon_json_format: {_parse_colon_json_format(text)}")
print(f"_parse_xml_tool_call: {_parse_xml_tool_call(text)}")
print(f"_parse_plain_tool_call: {_parse_plain_tool_call(text)}")
print()

print("=" * 60)
print("TEST 7: Direct to dispatch with empty tool_calls but text containing code")
print("=" * 60)
# Simulate a response that has both text AND tool_calls set
# (this can happen if brain.py parses something into tool_calls AND the raw text is there)
resp7 = LLMResponse(
    text="```bash\n...\n```",
    tool_calls=[]  # Empty - no native tool calls
)
result7 = dispatch(resp7)
print(f"Result type: {type(result7).__name__}")
print(f"Result: {result7}")