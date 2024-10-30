"""Http3 transport configuration."""

import logging

from aries_cloudagent.config.base import BaseSettings
from aries_cloudagent.config.plugin_settings import PluginSettings
from aries_cloudagent.config.settings import Settings
from pydantic import BaseModel

LOGGER = logging.getLogger(__name__)

PLUGIN_KEYS = {"httpxtransport"}

class HttpxConfig(BaseModel):

    force_close: bool = False
    keepalive_timeout: float = 15.0

    @classmethod
    def default(cls):
        """Return default configuration."""
        return cls(
            force_close=False,
            keepalive_timeout=15.0
        )


def get_config(root_settings: BaseSettings) -> HttpxConfig:
    """Retrieve producer configuration from settings."""
    assert isinstance(root_settings, Settings)

    settings = PluginSettings()
    for key in PLUGIN_KEYS:
        settings = PluginSettings.for_plugin(root_settings, key, None)
        if len(settings) > 0:
            break

    if len(settings) > 0:
        config = HttpxConfig(**settings)
    else:
        LOGGER.warning("Using default configuration")
        config = HttpxConfig.default()

    return config