"""Constants for retro_state."""
# Base component constants
DOMAIN = "retro_state"
DOMAIN_DATA = "{}_data".format(DOMAIN)
VERSION = "1.0.0"
PLATFORMS = [
    "recorder"
]
REQUIRED_FILES = [
    "const.py",
    "manifest.json",
    "recorder.py"
]
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

# Operational
EVENT_HISTORIC_STATE_CHANGED = 'historic_state_changed'

# Icons
ICON = "mdi:database-refresh"

# Device classes
BINARY_SENSOR_DEVICE_CLASS = "connectivity"

# Configuration
CONF_RECORDER_INTEGRATION = "recorder"

# Defaults
DEFAULT_NAME = DOMAIN
