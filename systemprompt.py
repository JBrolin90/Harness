import os
from AGENT import AGENT_md_INGESTIOR


def build_system_prompt() -> str:
    """Build system prompt from project.md."""
    project_text = ""
    project_path = os.path.join(os.getcwd(), "project.md")
    if os.path.isfile(project_path):
        try:
            with open(project_path, 'r') as f:
                project_text = f"\n\nProject Context (project.md):\n{f.read()}"
        except Exception:
            pass

    return f"""
    You are Bob, a helpful AI assistant.{project_text}
    Current Working Directory: {os.getcwd()}
    
    You have access to tools (provided via the API's function calling interface).
    When you need to use a tool, respond with a tool call - the API will handle it automatically.
    
    {AGENT_md_INGESTIOR()}
    """