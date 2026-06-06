"""Debug test to trace how '...' becomes a bash command - part 3.

The key question: does the LLM itself output '```bash\\n...\\n```' in its text response?
If so, brain.py's response.text would contain this, and dispatch() would parse and execute it.

But the debug output we saw shows the harness intercepted it BEFORE calling dispatch()
because the output shows "Bob REQUESTS SHELL EXECUTION" - that happens when
tool_dispatch.dispatch() returns a ToolResult for a bash call.

Let me check the controller flow more carefully and see if there's any path where
'...' could be passed as a command to bash without going through parse_bash_command.
"""
import sys
sys.path.insert(0, '/home/joachim/lab/prj/Harness')

from llm.response import LLMResponse, ToolCall
from tool_dispatch import dispatch, _safe_dispatch

# Monkey-patch _safe_dispatch to trace calls
original_safe_dispatch = _safe_dispatch

def traced_safe_dispatch(tool_name, arguments):
    print(f"  [TRACE] _safe_dispatch called with tool_name={repr(tool_name)}, arguments={repr(arguments)}")
    return original_safe_dispatch(tool_name, arguments)

import tool_dispatch
tool_dispatch._safe_dispatch = traced_safe_dispatch

# Set up mock bash tool
from tools.base_tool import BaseTool

class MockBashTool(BaseTool):
    name = "bash"
    description = ""
    parameters = {"type": "object", "properties": {}, "required": []}
    def execute(self, **kw):
        return f"[EXECUTED: bash with {kw}]"

BaseTool._registry["bash"] = MockBashTool


print("=" * 60)
print("SCENARIO: LLM outputs text with '```bash\\n...\\n```'")
print("=" * 60)
print("\nSimulating: response.text = '```bash\\n...\\n```'")
print("             response.tool_calls = []")
print("             response.error = None")
print()

resp = LLMResponse(text="```bash\n...\n```", tool_calls=[], error=None)
print(f"resp.has_tool_calls = {resp.has_tool_calls}")
print(f"resp.first_tool_call = {resp.first_tool_call}")
print()

print("Calling dispatch(resp)...")
result = dispatch(resp)
print(f"\nResult: {type(result).__name__} = {result}")
print()

print("=" * 60)
print("SCENARIO: Native tool_calls has 'bash' with '...' command")  
print("=" * 60)
print("\nSimulating: response.tool_calls = [ToolCall(name='bash', arguments={'command': '...'})]")
print("             response.text = ''")
print()

resp2 = LLMResponse(text="", tool_calls=[ToolCall(name="bash", arguments={"command": "..."})])
print(f"resp.has_tool_calls = {resp2.has_tool_calls}")
print(f"resp.first_tool_call = {resp2.first_tool_call}")
print()

print("Calling dispatch(resp)...")
result2 = dispatch(resp2)
print(f"\nResult: {type(result2).__name__} = {result2}")
print()

print("=" * 60)
print("KEY INSIGHT: Both paths lead to bash being executed.")
print("=" * 60)
print("""
If the model outputs '```bash\\n...\\n```' in its TEXT response:
  -> dispatch() tries native tool_calls first (empty)
  -> Falls through to parsers, parse_bash_command matches
  -> _safe_dispatch called with ('bash', {'command': '...'})

If the model uses native function calling with 'bash' as tool name:
  -> dispatch() sees response.has_tool_calls = True
  -> Calls _execute_call('bash', {'command': '...'}) directly
  -> _safe_dispatch called with ('bash', {'command': '...'})
""")