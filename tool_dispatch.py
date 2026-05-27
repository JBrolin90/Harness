"""Tool dispatch - parses JSON or XML tool calls and executes them."""
import json
import re
from tools.base_tool import BaseTool


def _parse_xml_tool_call(text: str) -> dict | None:
    """Parse XML-style tool call - handles multiple arg_key/arg_value pairs and no-arg calls."""
    # Match the tool_call block with lazy matching
    pattern = r'<tool_call>(.*?)</tool_call>'
    match = re.search(pattern, text.strip(), re.DOTALL)
    if not match:
        # Try matching tool_call with just a tool name (no closing tag, args come after)
        simple_pattern = r'<tool_call>\s*(\w+)'
        simple_match = re.search(simple_pattern, text.strip())
        if simple_match:
            tool_name = simple_match.group(1).strip()
            if tool_name and tool_name not in ("arg_key", "arg_value"):
                return {"name": tool_name, "arguments": {}}
        return None
    
    tool_content = match.group(1).strip()
    
    try:
        # Parse tool name (first word before any whitespace or tag)
        parts = tool_content.split('>')
        tool_name = parts[0].strip()
        
        # Get ALL arg_key and arg_value pairs
        arg_keys = re.findall(r'<arg_key>\s*(\w+)\s*</arg_key>', tool_content)
        arg_values = re.findall(r'<arg_value>\s*(.*?)\s*</arg_value>', tool_content, re.DOTALL)
        
        if arg_keys and arg_values:
            # Combine key-value pairs
            arguments = {}
            for key, value in zip(arg_keys, arg_values):
                arguments[key] = value.strip()
            return {"name": tool_name, "arguments": arguments}
        elif tool_name and tool_name not in ("arg_key", "arg_value"):
            # No args, just tool name
            return {"name": tool_name, "arguments": {}}
    except Exception:
        pass
    
    return None


def _parse_colon_json_format(text: str) -> dict | None:
    """Parse format like <tool_name>name:{args}/> or <tool_name>:{args}/>."""
    # First extract inner content of the XML tag
    inner_match = re.match(r'<\w+>(.+?)/?\s*>?\s*$', text.strip())
    if not inner_match:
        return None
    
    content = inner_match.group(1).strip()
    
    # Remove trailing / if present
    if content.endswith('/'):
        content = content[:-1].strip()
    
    # Split on first : to get tool name and args
    if ':' not in content:
        return None
    
    parts = content.split(':', 1)
    tool_name = parts[0].strip()
    args_str = parts[1].strip()
    
    # Remove surrounding { } if present
    args_str = args_str.strip().strip('{}').strip()
    
    if not args_str:
        return None
    
    # Try to parse as JSON
    try:
        args = json.loads(f'{{{args_str}}}')
        if isinstance(args, dict):
            return {"name": tool_name, "arguments": args}
    except json.JSONDecodeError:
        pass
    
    # Try parsing key: "value" pairs manually
    pairs = re.findall(r'(\w+):\s*"([^"]+)"', args_str)
    if pairs:
        return {"name": tool_name, "arguments": dict(pairs)}
    
    return None


def _parse_plain_tool_call(text: str) -> dict | None:
    """Parse simple name-only tool calls like <list_files>path</list_files>."""
    pattern = r'<(\w+)>\s*([^\<]+)\s*</\1>'
    match = re.search(pattern, text.strip())
    if match:
        tool_name = match.group(1)
        arg_value = match.group(2).strip()
        # Infer argument name from tool
        tool_args = {
            "read_file": "path",
            "write_file": "path",
            "edit_file": "path",
            "list_files": "path",
            "bash": "command",
            "get_model_name": "path",
        }
        arg_name = tool_args.get(tool_name, "path")
        return {"name": tool_name, "arguments": {arg_name: arg_value}}
    return None


def _dispatch_tool(tool_name: str, arguments: dict) -> str:
    """Execute a tool and return result with parameter normalization."""
    # Normalize common parameter name variations
    param_mapping = {
        "file_path": "path",
        "filename": "path",
        "directory": "path",
        "file_content": "content",
        "old_text": "search",
        "new_text": "replace",
        "cmd": "command",
    }
    normalized = {
        param_mapping.get(k, k): v for k, v in arguments.items()
    }
    return BaseTool.dispatch(tool_name, normalized)


def _parse_simple_tool_json(text: str) -> dict | None:
    """Parse simple tool format like {"tool":"name","args":{}}."""
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


def _parse_bash_command(text: str) -> dict | None:
    """Parse bash command from markdown code blocks like ```bash ... ```."""
    pattern = r'```(?:bash|sh)?\s*\n?(.*?)\n?```'
    match = re.search(pattern, text.strip(), re.DOTALL)
    if match:
        command = match.group(1).strip()
        if command:
            return {"name": "bash", "arguments": {"command": command}}
    return None


def tool_dispatch(response: str) -> str | None:
    """Parse response for tool call (JSON or XML format) and execute it."""
    # Try bash command in markdown code blocks first
    try:
        bash_call = _parse_bash_command(response)
        if bash_call:
            print(f"\n[🔧 Harness executing: bash]")
            return _dispatch_tool(bash_call["name"], bash_call["arguments"])
    except (KeyError, TypeError) as e:
        return f"[SYSTEM ERROR: {str(e)}]"
    except Exception as e:
        return f"[SYSTEM ERROR: {str(e)}]"

    # Try simple tool format: {"tool":"name","args":{}}
    try:
        simple = _parse_simple_tool_json(response)
        if simple:
            print(f"\n[🔧 Harness executing: {simple['name']}]")
            return _dispatch_tool(simple["name"], simple["arguments"])
    except (KeyError, TypeError) as e:
        return f"[SYSTEM ERROR: {str(e)}]"
    except Exception as e:
        return f"[SYSTEM ERROR: {str(e)}]"

    # Try JSON format first
    try:
        call = json.loads(response.strip())
        if "name" in call:
            tool_name = call["name"]
            arguments = call.get("arguments") or {}
            print(f"\n[🔧 Harness executing: {tool_name}]")
            return _dispatch_tool(tool_name, arguments)
    except json.JSONDecodeError:
        pass  # Not JSON, try other formats
    except (KeyError, TypeError) as e:
        return f"[SYSTEM ERROR: {str(e)}]"
    except Exception as e:
        return f"[SYSTEM ERROR: {str(e)}]"

    # Try colon JSON format: <tool_name>name:{args}/> or <tool>:{args}/>
    try:
        json_call = _parse_colon_json_format(response)
        if json_call:
            print(f"\n[🔧 Harness executing: {json_call['name']}]")
            return _dispatch_tool(json_call["name"], json_call["arguments"])
    except (KeyError, TypeError) as e:
        return f"[SYSTEM ERROR: {str(e)}]"
    except Exception as e:
        return f"[SYSTEM ERROR: {str(e)}]"

    # Try XML tool_call format
    try:
        xml_call = _parse_xml_tool_call(response)
        if xml_call:
            print(f"\n[🔧 Harness executing: {xml_call['name']}]")
            return _dispatch_tool(xml_call["name"], xml_call["arguments"])
    except (KeyError, TypeError) as e:
        return f"[SYSTEM ERROR: {str(e)}]"
    except Exception as e:
        return f"[SYSTEM ERROR: {str(e)}]"

    # Try simple XML format
    try:
        simple_call = _parse_plain_tool_call(response)
        if simple_call:
            print(f"\n[🔧 Harness executing: {simple_call['name']}]")
            return _dispatch_tool(simple_call["name"], simple_call["arguments"])
    except (KeyError, TypeError) as e:
        return f"[SYSTEM ERROR: {str(e)}]"
    except Exception as e:
        return f"[SYSTEM ERROR: {str(e)}]"

    return None