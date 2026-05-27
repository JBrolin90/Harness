"""Tool dispatch - parses JSON tool calls and executes them."""
import json
from tools.base_tool import BaseTool


def tool_dispatch(response: str) -> str | None:
    """Parse response for JSON tool call and execute it."""
    try:
        # Parse the response as JSON
        call = json.loads(response.strip())
        
        if "name" not in call:
            return None
        tool_name = call["name"]
        arguments = call.get("arguments") or {}
        
        print(f"\n[🔧 Harness executing: {tool_name}]")
        return BaseTool.dispatch(tool_name, arguments)
        
    except json.JSONDecodeError:
        return None
    except KeyError as e:
        return f"[SYSTEM ERROR: Missing parameter {e}]"
    except Exception as e:
        return f"[SYSTEM ERROR: {str(e)}]"
