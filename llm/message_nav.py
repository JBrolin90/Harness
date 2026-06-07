"""Dot-notation message navigation utilities."""
from typing import Any


EMPTY_CHOICES_SENTINEL = "__EMPTY_CHOICES__"


def navigate_to_message(data: dict, message_key: str) -> Any:
    """Navigate to message using dot-notation path.
    
    Args:
        data: Response dictionary from API.
        message_key: Dot-notation path (e.g., "choices[0].message" or "message").
    
    Returns:
        Message dict if found, None if path doesn't exist,
        or EMPTY_CHOICES_SENTINEL for empty choices array.
    
    Examples:
        navigate_to_message(data, "choices[0].message")  # -> message dict
        navigate_to_message(data, "message")              # -> message dict
    """
    parts = message_key.split(".")
    current = data
    for part in parts:
        if "[" in part and part.endswith("]"):
            key, idx_str = part.split("[")
            idx = int(idx_str.rstrip("]"))
            if isinstance(current, dict) and key in current:
                arr = current[key]
                # Handle empty choices array - treat as empty response (not error)
                if arr is None or (isinstance(arr, list) and len(arr) == 0):
                    return EMPTY_CHOICES_SENTINEL
                if isinstance(arr, list) and len(arr) > idx:
                    current = arr[idx]
                else:
                    return None
            else:
                return None
        elif isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


def is_empty_choices(result: Any) -> bool:
    """Check if navigation result is the empty choices sentinel."""
    return result == EMPTY_CHOICES_SENTINEL