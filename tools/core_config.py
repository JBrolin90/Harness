"""Core configuration for tools - uses ProviderConfig from provider.py."""
from provider import ProviderConfig

# Re-export for convenience
__all__ = ["ProviderConfig", "current_provider_config", "set_current_provider"]

# Global reference to the current provider config
current_provider_config: ProviderConfig | None = None


def set_current_provider(config: ProviderConfig):
    """Set the current provider configuration."""
    global current_provider_config
    current_provider_config = config
