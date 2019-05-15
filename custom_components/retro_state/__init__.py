"""
Component to integrate with retro_state.

For more details about this component, please refer to
https://gitlab.com/jbeckman/retro_state
"""
import logging
import os

import homeassistant.helpers.config_validation as cv
import voluptuous as vol

from . import recorder as retro_recorder
from .const import (
    DOMAIN_DATA,
    DOMAIN,
    ISSUE_URL,
    PLATFORMS,
    REQUIRED_FILES,
    STARTUP,
    VERSION,
    CONF_RECORDER_INTEGRATION,
    DEFAULT_NAME,
)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_RECORDER_INTEGRATION, default=False): cv.boolean
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Set up retro_state and all of the enabled integrations"""
    startup = STARTUP.format(name=DOMAIN, version=VERSION, issueurl=ISSUE_URL)
    _LOGGER.info(startup)

    # Check that all required files are present
    file_check = await check_files(hass)
    if not file_check:
        return False

    # Create DATA dict
    hass.data[DOMAIN_DATA] = {}

    if not PLATFORMS:
        _LOGGER.warning("You have enabled {}, but not any integrations.".format(DOMAIN))

    for platform in PLATFORMS:
        # Get platform specific configuration
        platform_config = config[DOMAIN].get(platform, {})

        # If platform is not enabled, skip.
        if not platform_config:
            continue

        setup_integration(hass, config, platform, platform_config)

    return True


def setup_integration(hass, config, platform, platform_config):
    _LOGGER.info("The {} integration for {} is enabled. Setting it up".format(platform, DOMAIN))

    if platform == "recorder":
        retro_recorder.setup(hass, config)
    else:
        _LOGGER.warning("{} has not implemented the integration {}".format(DOMAIN, platform))


async def check_files(hass):
    """Return bool that indicates if all files are present."""
    # Verify that the user downloaded all files.
    base = "{}/custom_components/{}/".format(hass.config.path(), DOMAIN)
    missing = []
    for file in REQUIRED_FILES:
        fullpath = "{}{}".format(base, file)
        if not os.path.exists(fullpath):
            missing.append(file)

    if missing:
        _LOGGER.critical("The following files are missing: %s", str(missing))
        returnvalue = False
    else:
        returnvalue = True

    return returnvalue
