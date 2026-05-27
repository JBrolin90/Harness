"""Tool that returns the name of the current LLM model."""
from .base_tool import BaseTool
from .core_config import current_provider_config


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
        if current_provider_config is None:
            return "[SYSTEM OUTPUT: No model configured]"
        model_name = current_provider_config.model
        return f"[SYSTEM OUTPUT: Current model is '{model_name}']"
