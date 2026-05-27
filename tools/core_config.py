"""Core configuration for tools - uses ProviderConfig from provider.py."""
from provider import ProviderConfig

# Re-export for convenience
__all__ = ["ProviderConfig", "current_provider_config", "set_current_provider", "get_current_model_name"]

# Global reference to the current provider config
current_provider_config: ProviderConfig | None = None

# Lazy accessor function to get the model name
def get_current_model_name() -> str | None:
    """Return the model name from the current provider config, if set."""
    return current_provider_config.model if current_provider_config else None


def set_current_provider(config: ProviderConfig):
    """Set the current provider configuration."""
    global current_provider_config
    current_provider_config = config
