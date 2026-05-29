"""Tool that returns the name of the current LLM model."""
from .base_tool import BaseTool
from .core_config import get_current_model_name


class GetModelNameTool(BaseTool):
    """Return the name of the current LLM model being used."""

    name = "get_model_name"
    description = "Get the name of the LLM model currently in use."
    parameters = {
        "type": "object",
        "properties": {},
        "required": []
    }

    def execute(self) -> str:  # type: ignore[override]
        model_name = get_current_model_name()
        if model_name is None:
            return "[SYSTEM OUTPUT: No model configured]"
        return f"[SYSTEM OUTPUT: Current model is '{model_name}']"
