import subprocess
import os
import re
from dataclasses import dataclass, field
from tool_definitions import TOOL_REGEX_MAP


@dataclass
class ToolExecutionReport:
    """Structured report of tool execution results."""
    results: list[str] = field(default_factory=list)
    # Stores (tool_cmd, result_string, file_path_arg) for history compaction
    executed_details: list[tuple[str, str, str | None]] = field(default_factory=list)
    has_results: bool = False

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

class ToolEngine:
    """
    Manages the parsing and execution of tool calls from LLM responses.
    Handles both serial and parallel execution modes.
    """
    def __init__(self, tool_regex_map: dict = TOOL_REGEX_MAP):
        self._tool_regex_map = tool_regex_map

    def _parse_tool_calls(self, response: str, execution_mode: str) -> list[tuple[int, str, re.Match]]:
        """
        Finds all tool command matches in the response.
        Returns a list of (start_index, tool_cmd_type, re_match_object), sorted by position.

        For serial mode, returns only the first match (earliest in text).
        For parallel mode, returns all matches.
        """
        all_matches = []
        for cmd_type, pattern in self._tool_regex_map.items():
            flags = re.MULTILINE
            if "WRITE" in cmd_type or "EDIT" in cmd_type:
                flags |= re.DOTALL

            if execution_mode == "parallel":
                # Use finditer to catch multiple calls of the same type
                for m in re.finditer(pattern, response, flags):
                    all_matches.append((m.start(), cmd_type, m))
            else:
                # Serial mode: find first match for this regex pattern
                m = re.search(pattern, response, flags)
                if m:
                    all_matches.append((m.start(), cmd_type, m))

        # Sort by occurrence in the text for consistent execution order
        all_matches.sort(key=lambda x: x[0])

        if execution_mode == "serial" and all_matches:
            all_matches = all_matches[:1]

        return all_matches

    def _execute_serial(self, response: str) -> ToolExecutionReport:
        """
        Finds and executes the first tool command in the response.
        Returns a ToolExecutionReport.
        """
        parsed_calls = self._parse_tool_calls(response, "serial")
        if not parsed_calls:
            return ToolExecutionReport()

        _, tool_cmd, match = parsed_calls[0]
        file_path = match.group(2)

        result_str = ""
        if tool_cmd in ["!WRITE", "!EDIT"]:
            result_str = execute_tool(tool_cmd, file_path, response)
        else:
            result_str = execute_tool(tool_cmd, file_path)
        
        return ToolExecutionReport(
            results=[result_str],
            executed_details=[(tool_cmd, result_str, file_path)],
            has_results=True
        )

    def _execute_parallel(self, response: str) -> ToolExecutionReport:
        """
        Finds and executes ALL tool commands in the response.
        Returns a ToolExecutionReport.
        """
        parsed_calls = self._parse_tool_calls(response, "parallel")
        if not parsed_calls:
            return ToolExecutionReport()

        report = ToolExecutionReport()
        for _, tool_cmd, match in parsed_calls:
            file_path = match.group(2)
            result_str = ""
            if tool_cmd in ["!WRITE", "!EDIT"]:
                result_str = execute_tool(tool_cmd, file_path, response)
            else:
                result_str = execute_tool(tool_cmd, file_path)
            
            report.results.append(result_str)
            report.executed_details.append((tool_cmd, result_str, file_path))
        report.has_results = bool(report.results)
        return report

    def dispatch(self, response: str, execution_mode: str) -> ToolExecutionReport:
        if execution_mode == "parallel":
            return self._execute_parallel(response)
        return self._execute_serial(response)


def execute_tool(command, arg, content=""):
    """The 'Hands': Executes local commands based on LLM requests."""

    if command == "!READ":
        print(f"\n[🔧 Harness executing: {command} on {arg}]")
        try:
            validated_path = _validate_path(arg.strip())
            with open(validated_path, 'r') as f:
                file_content = f.read()
            return f"[SYSTEM OUTPUT: Content of {validated_path}]\n{file_content}"
        except Exception as e:
            return f"[SYSTEM ERROR: {str(e)}]"


    elif command == "!WRITE":
        print(f"\n[🔧 Harness executing: {command} on {arg}]")
        original_arg = arg.strip()
        try:
            validated_path = _validate_path(original_arg)
        except ValueError as e:
            return f"[SYSTEM ERROR: {str(e)}]"
        try:
            content_match = re.search(r'<<<WRITE_BLOCK>>>(.*?)(?:<<<|>>>)', content, re.DOTALL)
            if content_match:
                write_content = _strip_visual_newlines(content_match.group(1))
            else:
                return "[SYSTEM ERROR: Invalid !WRITE format. Use <<<WRITE_BLOCK>>> markers.]"
            with open(validated_path, 'w') as f:
                f.write(write_content)
            return f"[SYSTEM OUTPUT: Successfully wrote {len(write_content)} characters to {validated_path}]"
        except Exception as e:
            return f"[SYSTEM ERROR: Could not write to {original_arg}: {str(e)}]"

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
        original_arg = arg.strip()
        try:
            validated_path = _validate_path(original_arg)
        except ValueError as e:
            return f"[SYSTEM ERROR: {str(e)}]"
        try:
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
            return f"[SYSTEM ERROR: Could not edit {original_arg}: {str(e)}]"
    return "[SYSTEM ERROR: Unknown command]"