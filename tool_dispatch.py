"""Tool dispatch - parses LLMResponse for tool calls and executes them."""
import json
import re
from tools.base_tool import BaseTool
from llm.response import LLMResponse, ToolResult, SystemError, NoToolFound
from logger import debug, error as log_error, is_debug_enabled


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
    
    # Guard against mismatched key/value counts (Issue #6)
    if len(keys) != len(values):
        return None  # Invalid format, don't produce malformed arguments
    
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

    inner = re.sub(r'^:?\s*', '', inner).strip()
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

    # Use first argument value as single argument (e.g., <bash>ls -la</bash>)
    # Parameter name will be normalized by _safe_dispatch → _normalize_arguments
    return {"name": tool_name, "arguments": {"content": inner}}


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


def _find_json_in_text(text: str) -> dict | None:
    """Find and parse a JSON object embedded in text.
    
    Uses bracket counting to handle nested JSON objects.
    Handles cases where model outputs text like: 'Here's the tool: {"name": ...}'
    without code fences.
    """
    # Bracket counting approach to find JSON objects
    depth = 0
    start = None
    in_string = False
    escape_next = False
    
    for i, c in enumerate(text):
        if escape_next:
            escape_next = False
            continue
        if c == '\\':
            escape_next = True
            continue
        if c == '"' and not escape_next:
            in_string = not in_string
            continue
        if in_string:
            continue
            
        if c == '{':
            if depth == 0:
                start = i
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0 and start is not None:
                try:
                    candidate = text[start:i+1]
                    data = json.loads(candidate)
                    if isinstance(data, dict) and ('name' in data or 'tool' in data):
                        return data
                except json.JSONDecodeError:
                    pass
                start = None
    
    return None


def _parse_json_raw(text: str) -> dict | None:
    """Parse bare JSON object or find JSON in text."""
    # First try to parse entire text as JSON
    try:
        data = json.loads(text.strip())
        if isinstance(data, dict) and "name" in data:
            return {"name": data["name"], "arguments": data.get("arguments", {})}
    except json.JSONDecodeError:
        pass
    
    # If that fails, try to find JSON object embedded in text
    data = _find_json_in_text(text)
    if data:
        if "name" in data:
            return {"name": data["name"], "arguments": data.get("arguments", {})}
        if "tool" in data:
            tool_name = data["tool"]
            if "args" in data:
                return {"name": tool_name, "arguments": data["args"]}
            if "arguments" in data:
                return {"name": tool_name, "arguments": data["arguments"]}
            # Use remaining fields as arguments
            args = {k: v for k, v in data.items() if k != "tool"}
            return {"name": tool_name, "arguments": args}
    
    return None


def parse_bash_command(text: str) -> dict | None:
    """Parse bash/sh code block into a bash tool call."""
    m = re.search(r'```(?:bash|sh)\s*\n?(.*?)\n?```', text.strip(), re.DOTALL)
    if m:
        command = m.group(1).strip()
        if command:
            return {"name": "bash", "arguments": {"command": command}}
    return None


def _parse_simple_tool_json(text: str) -> dict | None:
    """Parse {"tool": "name", "args": {...}} or {"tool": "name", "arguments": {...}}."""
    try:
        data = json.loads(text.strip())
        if isinstance(data, dict) and "tool" in data:
            tool_name = data["tool"]
            # Check for args or arguments key
            if "args" in data:
                return {"name": tool_name, "arguments": data["args"]}
            if "arguments" in data:
                return {"name": tool_name, "arguments": data["arguments"]}
            # Otherwise, use all other keys as arguments
            args = {k: v for k, v in data.items() if k != "tool"}
            if args:
                return {"name": tool_name, "arguments": args}
    except json.JSONDecodeError:
        pass
    return None


# ---------------------------------------------------------------------------
# Text-based parsers (for smaller models that may not use structured tool calls)
# These parsers interpret text output as potential tool calls - use with caution
#
# Parser precedence rationale (in order):
#   1. json-codeblock  - Fenced JSON (```json ...```). Most specific format, highest confidence.
#   2. json-raw        - Bare JSON object ({...}). Common for structured tool calls.
#   3. simple-json     - Alternative JSON format ({"tool": ..., "args": {...}}).
#   4. bash-block      - Bash/sh code block (```bash ...```). Common in model outputs.
#                        Placed high because smaller models may use markdown for commands.
#   5. tool_call-xml   - Explicit XML format (<tool_call>...<arg_key>...<arg_value>...</tool_call>).
#                        More verbose but unambiguous - placed before colon-xml.
#   6. colon-xml       - Colon format (<tool>:{...}). Shorthand that can overlap with other formats.
#   7. plain-xml       - Simple XML tag (<tool>value</tool>). Fallback for basic cases.
#
# Note: JSON parsers (1-3) are NOT redundant - codeblock vs raw are distinct formats.
# The ordering is arbitrary but functional for smaller models that use text-based tool calls.
_TEXT_PARSERS = [
    ("json-codeblock", extract_json_string),
    ("json-raw", _parse_json_raw),
    ("simple-json", _parse_simple_tool_json),
    ("bash-block", parse_bash_command),
    ("tool_call-xml", _parse_xml_tool_call),  # More explicit, checked before colon-xml
    ("colon-xml", _parse_colon_json_format),
    ("plain-xml", _parse_plain_tool_call),
]


def _check_multi_tool_call(response: LLMResponse) -> SystemError | None:
    """Check for multiple tool calls and return SystemError if found.
    
    Multiple tool calls require user confirmation before execution.
    
    Returns:
        SystemError if multiple tool calls detected, None otherwise.
    """
    if len(response.tool_calls) > 1:
        tool_names = [tc.name for tc in response.tool_calls]
        return SystemError(
            f"[SYSTEM ERROR: Multiple tool calls detected ({len(response.tool_calls)}). "
            f"Tools: {', '.join(tool_names)}. "
            f"User confirmation required to proceed.]"
        )
    return None


def dispatch(response: LLMResponse) -> ToolResult | SystemError | NoToolFound:
    """Parse response for tool call and execute it.

    For large/cloud models (MiniMax, OpenAI, etc.) that use structured tool calls.
    This function ONLY handles native tool_calls from the model response.
    Text responses are NOT parsed as commands.

    For smaller models that may output tool calls in text format, use
    dispatch_with_text_parsing() instead.

    Returns:
      ToolResult  - tool executed successfully (truthy, loop continues)
      SystemError - system-level error (falsy, loop stops)
      NoToolFound - no tool call found (falsy, loop stops)
    """
    if response.error:
        return SystemError(response.error)

    # Check for multiple tool calls (requires confirmation)
    multi_error = _check_multi_tool_call(response)
    if multi_error:
        return multi_error

    # Native tool calls only - structured tool calls from the model
    if response.has_tool_calls:
        tc = response.first_tool_call
        if tc:
            return _execute_call(tc.name, tc.arguments)

    # No text parsing - large models should use structured tool calls
    return NoToolFound()


def dispatch_with_text_parsing(response: LLMResponse) -> ToolResult | SystemError | NoToolFound:
    """Parse response for tool call using both native tool_calls AND text parsers.

    For smaller models that may not consistently use structured tool calls and
    instead output tool calls in text format (e.g., <bash>ls</bash> or ```bash ls```).

    WARNING: This interprets any text that looks like a tool call as a command
    to execute. Only use with models that you trust to not output markdown code
    blocks that could be misinterpreted as commands.

    Returns:
      ToolResult  - tool executed successfully (truthy, loop continues)
      SystemError - system-level error (falsy, loop stops)
      NoToolFound - no tool call found (falsy, loop stops)
    """
    if response.error:
        return SystemError(response.error)

    # Check for multiple tool calls (requires confirmation)
    multi_error = _check_multi_tool_call(response)
    if multi_error:
        return multi_error

    # 1. Native tool calls
    if response.has_tool_calls:
        tc = response.first_tool_call
        if tc:
            return _execute_call(tc.name, tc.arguments)

    # 2. String parsing fallback
    if not response.text:
        return NoToolFound()

    for parser_name, parser in _TEXT_PARSERS:
        try:
            call = parser(response.text)
            if call:
                return _execute_call(call["name"], call["arguments"])
        except Exception as e:
            debug(f"Parser '{parser_name}' failed: {e}", module="tool_dispatch")
            continue

    return NoToolFound()


def _execute_call(tool_name: str, arguments: dict) -> ToolResult | SystemError:
    """Internal helper to execute a tool and wrap the result."""
    if is_debug_enabled():
        debug(f"Executing tool: {tool_name} with args: {json.dumps(arguments)}", module="tool_dispatch")
    else:
        print(f"\n[🔧 Harness executing: {tool_name}]")
    try:
        output = _safe_dispatch(tool_name, arguments)
    except (TypeError, KeyError, ValueError) as e:
        # Catch TypeError (invalid arguments), KeyError (missing fields), ValueError (invalid values)
        return SystemError(f"[SYSTEM ERROR: Invalid arguments for '{tool_name}': {e}]")
    except Exception as e:
        # Catch any other unexpected exceptions to prevent crashes
        log_error(f"Unexpected error in '{tool_name}': {e}", module="tool_dispatch")
        return SystemError(f"[SYSTEM ERROR: Unexpected error in '{tool_name}': {e}]")

    if output.startswith("[SYSTEM ERROR"):
        log_error(f"Tool '{tool_name}' returned system error: {output}", module="tool_dispatch")
        return SystemError(output)

    if is_debug_enabled():
        debug(f"Tool '{tool_name}' completed successfully, output length: {len(output)}", module="tool_dispatch")

    return ToolResult(tool_name, output)


def dispatch_iteration(responses: list[LLMResponse]) -> list[ToolResult | SystemError | NoToolFound]:
    """Process a list of responses (multi-choice) and execute tools.
    
    Returns:
        List of results matching input responses length. Each element is:
          ToolResult   - tool executed successfully
          SystemError  - system-level error (loop stops after this)
          NoToolFound  - no tool call found in this response
    """
    results = []
    for resp in responses:
        res = dispatch(resp)
        results.append(res)
        if isinstance(res, SystemError):
            break  # Stop processing if a SystemError occurs
    return results

# Backward compatibility alias
tool_dispatch = dispatch
