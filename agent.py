"""Agent configuration loader."""

import config

# Lazy loading to avoid duplicate reads during import
_AGENT_PY = None


def _get_agent_py():
    global _AGENT_PY
    if _AGENT_PY is None:
        _AGENT_PY = config.load("AGENT.py")
    return _AGENT_PY


# For backward compatibility - access via function in systemprompt.py
def get_agent_py():
    return _get_agent_py()
