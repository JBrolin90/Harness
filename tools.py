import subprocess
import os
import re

def get_tools_instructions():
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

def _validate_path(file_path: str) -> str:
    """
    Validates that the given file_path is within the current working directory
    or a subdirectory thereof, and returns its absolute, normalized path.
    Raises ValueError if the path is outside the allowed directory.
    """
    current_working_directory = os.getcwd()
    abs_path = os.path.abspath(os.path.join(current_working_directory, file_path))

    if not abs_path.startswith(current_working_directory):
        raise ValueError(f"Access denied: Path '{file_path}' is outside the allowed working directory.")

    return abs_path

def _strip_visual_newlines(text):
    """Removes at most one leading and one trailing newline added by LLMs for 'visual clarity'."""
    if text.startswith('\n'): 
        text = text[1:]
    if text.endswith('\n'): 
        text = text[:-1]
    return text


def execute_tool(command, arg, content=""):
    """The 'Hands': Executes local commands based on LLM requests."""

    if command == "!READ":
        print(f"\n[🔧 Harness executing: {command} on {arg}]")
        try:
            validated_path = _validate_path(arg.strip())
            with open(validated_path, 'r') as f:
                content = f.read()
            return f"[SYSTEM OUTPUT: Content of {validated_path}]\n{content}"
        except Exception as e:
            return f"[SYSTEM ERROR: {str(e)}]"


    elif command == "!WRITE":
        print(f"\n[🔧 Harness executing: {command} on {arg}]")
        try:
            validated_path = _validate_path(arg.strip())
            # Parse new delimiter-based format: content is exactly between markers
            content_match = re.search(r'<<<WRITE_BLOCK>>>(.*?)(?:<<<|>>>)', content, re.DOTALL)
            if content_match:
                write_content = _strip_visual_newlines(content_match.group(1))
            else:
                return "[SYSTEM ERROR: Invalid !WRITE format. Use <<<WRITE_BLOCK>>> markers.]"
            with open(validated_path, 'w') as f:
                f.write(write_content)
            return f"[SYSTEM OUTPUT: Successfully wrote {len(write_content)} characters to {validated_path}]"
        except Exception as e:
            return f"[SYSTEM ERROR: Could not write to {validated_path}: {str(e)}]"

    elif command == "!BASH":
        # Sanitize the input by stripping whitespace and quotation marks
        clean_arg = arg.strip().strip('"').strip("'")
        
        # Hardcoded whitelist for safe commands
        safe_commands_whitelist = ["ls", "cd", "find", "cat", "grep", "pwd", "du", "head", "tail", "wc", "stat", "diff"]
        
        # Extract the first word of the command to check against the whitelist
        first_command_word = clean_arg.split(' ')[0]

        # Check if the command is in the whitelist
        if first_command_word in safe_commands_whitelist:
            print(f"\n[🔧 Harness executing whitelisted !BASH command: {clean_arg}]")
            try:
                result = subprocess.run(clean_arg, shell=True, capture_output=True, text=True)
                output = (result.stdout + result.stderr).strip()
                print(f"\n[SPYING ON DATA FED TO LLM]:\n\n{output}\n--------------------------")
                return f"[SYSTEM OUTPUT: Bash executed with code {result.returncode}]\n{output}"
            except Exception as e:
                return f"[SYSTEM ERROR: Bash failed: {str(e)}]"
        else:
            # HUMAN IN THE LOOP SECURITY GATE for non-whitelisted commands
            print("\n⚠️  Bob REQUESTS SHELL EXECUTION ⚠️")
            print(f"Command:  {clean_arg}")
            confirm = input("Allow this command? [y/N]: ")

            if confirm.lower() == 'y':
                try:
                    # shell=True allows pipes and standard bash syntax
                    result = subprocess.run(clean_arg, shell=True, capture_output=True, text=True)
                    output = (result.stdout + result.stderr).strip()

                    print(f"\n[SPYING ON DATA FED TO LLM]:\n\n{output}\n--------------------------")

                    return f"[SYSTEM OUTPUT: Bash executed with code {result.returncode}]\n{output}"
                except Exception as e:
                    return f"[SYSTEM ERROR: Bash failed: {str(e)}]"
            else:
                print("[❌ Execution denied by user.]")
                return "[SYSTEM ERROR: The user denied permission to execute this bash command. You must try a different approach.]"

    elif command == "!LS":
        print(f"\n[🔧 Harness executing: {command} on {arg}]")
        try:
            validated_path = _validate_path(arg.strip())
            if not os.path.exists(validated_path):
                return f"[SYSTEM ERROR: Directory {validated_path} not found.]"
            files = os.listdir(validated_path)
            files.sort()
            return f"[SYSTEM OUTPUT: Files in {validated_path}]\n" + "\n".join(files)
        except Exception as e:
            return f"[SYSTEM ERROR: {str(e)}]"

    elif command == "!EDIT":
        print(f"\n[🔧 Harness executing: {command} on {arg}]")
        try:
            validated_path = _validate_path(arg.strip())
            if not os.path.exists(validated_path):
                return f"[SYSTEM ERROR: File {validated_path} not found.]"

            # Parse new delimiter-based format
            search_match = re.search(r'<<<SEARCH_BLOCK>>>(.*?)<<<REPLACE_BLOCK>>>', content, re.DOTALL)
            replace_match = re.search(r'<<<REPLACE_BLOCK>>>(.*?)(?:<<<|>>>)', content, re.DOTALL)

            if not search_match:
                return "[SYSTEM ERROR: Missing <<<SEARCH_BLOCK>>> marker in edit block.]"
            if not replace_match:
                return "[SYSTEM ERROR: Missing <<<REPLACE_BLOCK>>> or closing <<< marker.]"

            search_block = _strip_visual_newlines(search_match.group(1))
            replace_block = _strip_visual_newlines(replace_match.group(1))

            with open(validated_path, 'r') as f:
                file_content = f.read()

            if search_block not in file_content:
                return "[SYSTEM ERROR: Search block not found in file. Edit aborted to prevent data corruption.]"

            # Replace only the first occurrence for safety
            new_content = file_content.replace(search_block, replace_block, 1)

            with open(validated_path, 'w') as f:
                f.write(new_content)

            return f"[SYSTEM OUTPUT: Successfully edited {validated_path}]"
        except Exception as e:
            return f"[SYSTEM ERROR: Could not edit {validated_path}: {str(e)}]"
    return "[SYSTEM ERROR: Unknown command]"
