"""
Component to integrate with retro_state.

For more details about this component, please refer to
https://gitlab.com/jbeckman/retro_state
"""
import logging
import os

import homeassistant.helpers.config_validation as cv
import voluptuous as vol

from . import recorder as retro_recorder, influxdb as retro_influxdb
from .const import (
    DOMAIN_DATA,
    DOMAIN,
    ISSUE_URL,
    PLATFORMS,
    REQUIRED_FILES,
    STARTUP,
    VERSION,
    CONF_RECORDER_INTEGRATION,
    CONF_INFLUXDB_INTEGRATION,
    DEFAULT_NAME,
)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_RECORDER_INTEGRATION, default=False): cv.boolean,
                vol.Optional(CONF_INFLUXDB_INTEGRATION, default=False): cv.boolean
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

    # Provided retro_state integrations
    integrations = config[DOMAIN]

    enabled_integrations = 0

    for integration_key, integration_config in integrations.items():
        # Ensure the integration key is a supported integration. This should never be the case as Home Assistant
        # prevents invalid keys from occurring in the config
        if integration_key not in PLATFORMS:
            _LOGGER.warning("The provided integration {} is not supported by {}, perhaps there is a typo in "
                            "your config.".format(integration_key, DOMAIN))
            continue

        # If the integration is not enabled, skip it
        if not integration_config:
            continue

        enabled_integrations += 1
        setup_integration(hass, config, integration_key, integration_config)

    if not enabled_integrations:
        _LOGGER.warning("You have enabled {}, but not any integrations.".format(DOMAIN))

    return True


def setup_integration(hass, config, integration_key, integration_config):
    _LOGGER.info("The {} integration for {} is enabled. Setting it up...".format(integration_key, DOMAIN))

    if integration_key == retro_recorder.DOMAIN:
        retro_recorder.configure(hass, config)
    elif integration_key == retro_influxdb.DOMAIN:
        retro_influxdb.configure(hass, config)
    else:
        # Once again, should never get to this spot, but if HA changes we have a breadcrumb to help debug
        _LOGGER.warning("{} has not implemented the integration [{}].".format(DOMAIN, integration_key))


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
