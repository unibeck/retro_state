"""Constants for blueprint."""
# Base component constants
DOMAIN = "async_template"
DOMAIN_DATA = "{}_data".format(DOMAIN)
VERSION = "1.0.0"
PLATFORMS = ["sensor"]
REQUIRED_FILES = ["const.py", "sensor.py"]
ISSUE_URL = "https://github.com/custom-components/blueprint/issues"

STARTUP = """
-------------------------------------------------------------------
{name}
Version: {version}
This is a custom component
If you have any issues with this you need to open an issue here:
{issueurl}
-------------------------------------------------------------------
"""

# Operational
URL = "https://jsonplaceholder.typicode.com/todos/1"

# Icons
ICON = "mdi:format-quote-close"

# Device classes
BINARY_SENSOR_DEVICE_CLASS = "connectivity"

# Configuration
CONF_SENSOR = "sensor"
CONF_LAST_CHANGED_TEMPLATE = "last_changed_template"
CONF_LAST_UPDATED_TEMPLATE = "last_updated_template"

# Defaults
DEFAULT_NAME = DOMAIN
