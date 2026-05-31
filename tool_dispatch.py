"""Tool dispatch - parses LLMResponse for tool calls and executes them."""
import json
import re
from tools.base_tool import BaseTool
from response import LLMResponse, ToolResult, SystemError, NoToolFound


# ---------------------------------------------------------------------------
# Parameter normalization
# ---------------------------------------------------------------------------

def _normalize_arguments(arguments: dict) -> dict:
    """Normalize parameter names for common LLM aliases."""
    param_mapping: dict[str, str] = {
        "file_path": "path",
        "filename": "path",
        "directory": "path",
        "file_content": "content",
        "contentBody": "content",
        "old_text": "search",
        "new_text": "replace",
        "cmd": "command",
        "file_location": "path",
        "text": "content",
        "code": "content",
        "old_content": "search",
    }
    normalized = {param_mapping.get(k, k): v for k, v in arguments.items()}
    return normalized

def _safe_dispatch(tool_name: str, arguments: dict) -> str:
    """Execute a tool with normalized parameters and safe error handling."""
    normalized = _normalize_arguments(arguments)
    return BaseTool.dispatch(tool_name, normalized)


# ---------------------------------------------------------------------------
# Parser helpers
# ---------------------------------------------------------------------------

def _parse_xml_tool_call(text: str) -> dict | None:
    """Parse XML tool_call format.

    Handles:
      - <tool_call>tool_name</tool_call>                 (zero args)
      - <tool_call><tool_name><arg_key>...</arg_key>...</tool_call>  (wrapped with args)
      - <tool_call>tool_name<arg_key>...</arg_key>...</tool_call>  (bare with args)
    """
    text = text.strip()

    m = re.match(r'^<tool_call>\s*(\w+)\s*</tool_call>$', text)
    if m:
        return {"name": m.group(1), "arguments": {}}

    full_match = re.search(r'<tool_call>\s*(.*?)\s*</tool_call>', text, re.DOTALL)
    if not full_match:
        return None

    content = full_match.group(1).strip()

    before = re.split(r'<arg_key>', content)[0].strip().lstrip('<')
    name_match = re.match(r'^(\w+)', before)
    if not name_match:
        return None
    tool_name = name_match.group(1)
    if tool_name in ("arg_key", "arg_value"):
        return None

    keys = re.findall(r'<arg_key>\s*(\w+)\s*</arg_key>', content)
    values = re.findall(r'<arg_value>\s*(.*?)\s*</arg_value>', content, re.DOTALL)
    arguments = dict(zip(keys, [v.strip() for v in values]))

    return {"name": tool_name, "arguments": arguments}


def _parse_colon_json_format(text: str) -> dict | None:
    """Parse <tool_name>:{arg: val}/> or <tool_name>name:{arg: val}/>."""
    text = text.strip()

    m = re.match(r'^<(\w+)>(.*)</\1>\s*$', text, re.DOTALL)
    if not m:
        return None
    tool_name = m.group(1)
    inner = m.group(2).strip()

    if not inner:
        return {"name": tool_name, "arguments": {}}

    inner = re.sub(r'^:?\s*', '', inner).rstrip('/').strip()
    if not inner:
        return {"name": tool_name, "arguments": {}}

    # Parse the JSON content directly
    try:
        parsed = json.loads(inner)
        if isinstance(parsed, dict):
            return {"name": tool_name, "arguments": parsed}
    except json.JSONDecodeError:
        pass

    # Fallback: key: "value" pairs
    pairs = re.findall(r'(\w+):\s*"([^"]*)"', inner)
    if pairs:
        return {"name": tool_name, "arguments": dict(pairs)}

    return None


def _parse_plain_tool_call(text: str) -> dict | None:
    """Parse <tool>value</tool> or <tool></tool>."""
    text = text.strip()

    m_empty = re.match(r'^<(\w+)>\s*</\1>$', text)
    if m_empty:
        return {"name": m_empty.group(1), "arguments": {}}

    m = re.match(r'^<(\w+)>\s*([^\<]+)\s*</\1>$', text)
    if not m:
        return None

    tool_name = m.group(1)
    inner = m.group(2).strip()

    if tool_name in {"get_model_name", "list_loaded_tools"}:
        return {"name": tool_name, "arguments": {}}

    arg_map: dict[str, str] = {
        "read_file": "path",
        "write_file": "path",
        "edit_file": "path",
        "list_files": "path",
        "bash": "command",
    }
    arg_name = arg_map.get(tool_name, "path")
    return {"name": tool_name, "arguments": {arg_name: inner}}


def extract_json_string(text: str) -> dict | None:
    """Parse JSON inside ```json ... ```."""
    m = re.search(r'```json\s*\n?(.*?)\n?```', text.strip(), re.DOTALL)
    if not m:
        return None
    try:
        data = json.loads(m.group(1).strip())
        if isinstance(data, dict) and "name" in data:
            return {"name": data["name"], "arguments": data.get("arguments", {})}
    except json.JSONDecodeError:
        pass
    return None


def _parse_json_raw(text: str) -> dict | None:
    """Parse bare JSON object."""
    try:
        data = json.loads(text.strip())
        if isinstance(data, dict) and "name" in data:
            return {"name": data["name"], "arguments": data.get("arguments", {})}
    except json.JSONDecodeError:
        pass
    return None


def parse_bash_command(text: str) -> dict | None:
    """Parse bash/sh code block into a bash tool call."""
    m = re.search(r'```(?:bash|sh)?\s*\n?(.*?)\n?```', text.strip(), re.DOTALL)
    if m:
        command = m.group(1).strip()
        if command:
            return {"name": "bash", "arguments": {"command": command}}
    return None


def _parse_simple_tool_json(text: str) -> dict | None:
    """Parse {"tool": "name", "args": {...}}."""
    try:
        data = json.loads(text.strip())
        if isinstance(data, dict):
            if "tool" in data and "args" in data:
                return {"name": data["tool"], "arguments": data["args"]}
            if "tool" in data:
                return {"name": data["tool"], "arguments": data.get("args", {})}
    except json.JSONDecodeError:
        pass
    return None


# ---------------------------------------------------------------------------
# Dispatch pipeline
# ---------------------------------------------------------------------------

def dispatch(response: LLMResponse) -> ToolResult | SystemError | NoToolFound:
    """Parse response for tool call and execute it.

    Returns:
      ToolResult  - tool executed successfully (truthy, loop continues)
      SystemError - system-level error (falsy, loop stops)
      NoToolFound - no tool call found (falsy, loop stops)
    """
    if response.error:
        return SystemError(response.error)

    # 1. Native tool calls
    if response.has_tool_calls:
        tc = response.first_tool_call
        if tc:
            return _execute_call(tc.name, tc.arguments)

    # 2. String parsing fallback
    if not response.text:
        return NoToolFound()

    parsers = [
        ("json-codeblock", extract_json_string),
        ("json-raw", _parse_json_raw),
        ("simple-json", _parse_simple_tool_json),
        ("bash-block", parse_bash_command),
        ("colon-xml", _parse_colon_json_format),
        ("tool_call-xml", _parse_xml_tool_call),
        ("plain-xml", _parse_plain_tool_call),
    ]

    text = response.text
    for parser_name, parser in parsers:
        try:
            call = parser(text)
            if call:
                return _execute_call(call["name"], call["arguments"])
        except Exception as e:
            return SystemError(f"[DISPATCH PARSER '{parser_name}' ERROR: {e}]")

    return NoToolFound()


def _execute_call(tool_name: str, arguments: dict) -> ToolResult | SystemError:
    """Internal helper to execute a tool and wrap the result."""
    print(f"\n[🔧 Harness executing: {tool_name}]")
    output = _safe_dispatch(tool_name, arguments)

    if output.startswith("[SYSTEM ERROR"):
        return SystemError(output)

    return ToolResult(tool_name, output)


def dispatch_iteration(responses: list[LLMResponse]) -> list[ToolResult | SystemError]:
    """Process a list of responses (multi-choice) and execute tools."""
    results = []
    for resp in responses:
        res = dispatch(resp)
        if isinstance(res, (ToolResult, SystemError)):
            results.append(res)
        if isinstance(res, SystemError):
            break # Stop processing if a SystemError occurs
    return results

# Backw
# Backward compatibility alias
tool_dispatch = dispatch
