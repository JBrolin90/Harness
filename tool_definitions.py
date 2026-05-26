# Define regexes for tool detection
TOOL_REGEX_MAP = {
    "!WRITE": r'^\s*!(WRITE)\s+(\S+)',
    "!EDIT":  r'^\s*!(EDIT)\s+(\S+)',
    "!READ":  r'^\s*!(READ)\s+(\S+)',
    "!BASH":  r'^\s*!(BASH)\s+(.+)',
    "!LS":    r'^\s*!(LS)\s+(\S+)'
}

def get_tools_instructions() -> str:
    """
    Returns the detailed instructions for available tools, including their syntax
    and usage rules, to be included in the system prompt.
    """
    return """
        AVAILABLE TOOLS:
        1. Read a file:
        !READ /path/to/file

        2. Write a NEW file:
        !WRITE /path/to/file
        <<<WRITE_BLOCK>>>[FILE CONTENT]<<<
        
        3. Execute a bash command:
        !BASH your_command_here

        4. List files in a directory:
        !LS /path/to/directory

        5. Edit an existing file:
        !EDIT /path/to/file
        <<<SEARCH_BLOCK>>>[EXACT text to find]<<<REPLACE_BLOCK>>>[EXACT replacement text]<<<
        IMPORTANT: The text inside <<<SEARCH_BLOCK>>> and <<<REPLACE_BLOCK>>> must be EXACTLY what you want to find/replace. Do NOT add extra newlines or spaces for formatting unless they are part of the text you are searching for or replacing. For example, if you want to replace "original" with "updated", the format should be:
        <<<SEARCH_BLOCK>>>original<<<REPLACE_BLOCK>>>updated<<<
        NOT:
        <<<SEARCH_BLOCK>>>
        original
        <<<REPLACE_BLOCK>>>
        updated
        <<<

        RULES:
        - Do not use JSON to call tools. Use the exact text commands above.
        - For !WRITE, you MUST include the <<<WRITE_BLOCK>>> keyword. For !EDIT, you MUST include <<<SEARCH_BLOCK>>> and <<<REPLACE_BLOCK>>>. Every block must be closed with a final <<<.
        - Use !BASH for things like checking systemctl status, pinging devices, or validating YAML.
        - Wait for the system to confirm tool operations before concluding.
        - You are an AUTONOMOUS agent. Do not ask the user for confirmation after a tool call; the Harness will provide the output automatically.
        - Use relative paths based on the provided Working Directory unless an absolute path is required.
        - The single newline immediately following <<<WRITE_BLOCK>>> and the single newline immediately preceding the closing <<< are considered visual padding and are STRIPPED. To start or end a file with an intentional newline, add an extra one.
        - IMPORTANT: Only perform ONE tool call per response. Wait for the system output before proceeding to the next step.
    """