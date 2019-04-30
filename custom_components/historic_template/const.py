"""Constants for historic_template."""
# Base component constants
DOMAIN = "historic_template"
DOMAIN_DATA = "{}_data".format(DOMAIN)
VERSION = "1.0.0"
PLATFORMS = ["sensor"]
REQUIRED_FILES = ["const.py", "sensor.py", "historic_entity.py"]
ISSUE_URL = "https://gitlab.com/jbeckman/retro_state/issues"

STARTUP = """
-------------------------------------------------------------------
{name}
Version: {version}
This is a custom component
If you have any issues with this you need to open an issue here:
{issueurl}
-------------------------------------------------------------------
"""

# Icons
ICON = "mdi:clock-end"

# Configuration
CONF_SENSOR = "sensor"
CONF_LAST_CHANGED_TEMPLATE = "last_changed_template"
CONF_LAST_UPDATED_TEMPLATE = "last_updated_template"

# Defaults
DEFAULT_NAME = DOMAIN
