"""Debug test to trace how '...' becomes a bash command - part 2.

Investigate if brain.py could be producing tool_calls with name="..." or similar.
"""
import sys
sys.path.insert(0, '/home/joachim/lab/prj/Harness')

from llm.response import LLMResponse, ToolCall
from tool_dispatch import dispatch

# Clear and set up a mock bash tool
from tools.base_tool import BaseTool

class MockBashTool(BaseTool):
    name = "bash"
    description = ""
    parameters = {"type": "object", "properties": {}, "required": []}
    def execute(self, **kw):
        return f"[EXECUTED: bash with {kw}]"

class MockReadTool(BaseTool):
    name = "read_file"
    description = ""
    parameters = {"type": "object", "properties": {}, "required": []}
    def execute(self, **kw):
        return f"[EXECUTED: read_file with {kw}]"

BaseTool._registry["bash"] = MockBashTool
BaseTool._registry["read_file"] = MockReadTool


print("=" * 60)
print("TEST A: ToolCall with name='...' (empty but valid key)")
print("=" * 60)
resp_a = LLMResponse(tool_calls=[ToolCall(name="...", arguments={})])
result_a = dispatch(resp_a)
print(f"Result type: {type(result_a).__name__}")
print(f"Result: {result_a}")
print()

print("=" * 60)
print("TEST B: ToolCall with name='bash' and arg '...'")
print("=" * 60)
resp_b = LLMResponse(tool_calls=[ToolCall(name="bash", arguments={"command": "..."})])
result_b = dispatch(resp_b)
print(f"Result type: {type(result_b).__name__}")
print(f"Result: {result_b}")
print()

print("=" * 60)
print("TEST C: ToolCall with name='' (empty string) for bash")
print("=" * 60)
resp_c = LLMResponse(tool_calls=[ToolCall(name="", arguments={"command": "ls"})])
result_c = dispatch(resp_c)
print(f"Result type: {type(result_c).__name__}")
print(f"Result: {result_c}")
print()

print("=" * 60)
print("TEST D: Check what first_tool_call returns for these")
print("=" * 60)
for name, args in [
    ("...", {}),
    ("bash", {"command": "..."}),
    ("", {"command": "ls"}),
]:
    tc = ToolCall(name=name, arguments=args)
    print(f"ToolCall(name={repr(tc.name)}, args={tc.arguments}) -> first_tool_call.name = {repr(tc.name)}")

print()

print("=" * 60)
print("TEST E: _parse_tool_calls on a message dict with '...' as a name")
print("=" * 60)
from brain import _parse_tool_calls

# Simulate a message where tool_calls has '...' as name
message1 = {"tool_calls": [{"function": {"name": "...", "arguments": {}}}]}
result1 = _parse_tool_calls(message1)
print(f"_parse_tool_calls({message1}) = {result1}")

# What if it's a top-level function_call?
message2 = {"function_call": {"name": "...", "arguments": {}}}
result2 = _parse_tool_calls(message2)
print(f"_parse_tool_calls({message2}) = {result2}")

# What if tool_calls has name at top level (non-standard)?
message3 = {"tool_calls": [{"name": "...", "arguments": {}}]}
result3 = _parse_tool_calls(message3)
print(f"_parse_tool_calls({message3}) = {result3}")