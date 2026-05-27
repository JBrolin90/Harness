import os
from AGENT import AGENT_md_INGESTIOR


def build_system_prompt() -> str:
    """Build system prompt from project.md."""
    tools_snippets = """AVAILABLE TOOLS:
- read_file: Read file contents
- write_file: Create or overwrite files
- edit_file: Make precise file edits with exact text replacement
- list_files: List directory contents
- bash: Execute bash commands"""

    return f"""You are Bob, a helpful AI assistant.
Current Working Directory: {os.getcwd()}

{tools_snippets}

{AGENT_md_INGESTIOR()}
"""