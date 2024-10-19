import logging

from aries_cloudagent.config.injection_context import InjectionContext
from aries_cloudagent.core.plugin_registry import PluginRegistry

LOGGER = logging.getLogger(__name__)


async def setup(context: InjectionContext):
    """Setup script for connection_update."""
    LOGGER.info("> plugin setup...")

    plugin_registry = context.inject(PluginRegistry)
    if not plugin_registry:
        raise ValueError("PluginRegistry missing in context")

    LOGGER.info("< plugin setup.")
