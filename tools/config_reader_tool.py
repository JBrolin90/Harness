"""Configuration file reader tool."""
import config
from .base_tool import BaseTool


class ConfigReaderTool(BaseTool):
    """Read a configuration file from the predefined config directories."""

    name = "config_reader"
    description = "Read a configuration file by searching predefined directories. Use this tool when instructed to read a configuration file."
    parameters = {
        "type": "object",
        "properties": {
            "filename": {
                "type": "string",
                "description": "Name of the configuration file to read (e.g., 'memory_instructions.md', 'AGENT.py')."
            }
        },
        "required": ["filename"]
    }

    def execute(self, filename: str) -> str:  # type: ignore[override]
        content = config.load(filename)
        if content:
            print(f"\n[CONFIG READER] Loaded '{filename}' from config directories")
            return content
        else:
            print(f"\n[CONFIG READER] '{filename}' not found in any config directory")
            return ""
