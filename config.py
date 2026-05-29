"""Configuration file loader module."""

import os

# Predefined directories to search for config files (in order of priority)
CONFIG_DIRS = [
    ".",
    "/etc/harness",
    os.path.expanduser("~/.config/harness"),
]



def load(filename: str) -> str:
    """
    Load a configuration file from the first directory where it exists.

    Args:
        filename: Name of the config file to load.

    Returns:
        Contents of the file as a string, or "" if not found.
    """
    for directory in CONFIG_DIRS:
        filepath = os.path.join(directory, filename)
        if os.path.isfile(filepath):
            try:
                with open(filepath, "r") as f:
                    content = f.read()
                    return content
            except (IOError, OSError):
                continue
    return ""
