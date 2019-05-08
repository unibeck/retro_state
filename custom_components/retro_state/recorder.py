"""Integration with Recorder component from base Home Assistant."""

from custom_components.historic_template.historic_entity import HistoricEntity
from .const import DOMAIN_DATA, ICON


async def async_setup_platform(
    hass, config, async_add_entities, discovery_info=None
):  # pylint: disable=unused-argument
    """Setup sensor platform."""
    async_add_entities([Recorder(hass, discovery_info)], True)


class Recorder(HistoricEntity):
    """blueprint Sensor class."""

    def __init__(self, hass, config):
        self.hass = hass
        self.attr = {}
        self._state = None
        # TODO: Name does not exists. Instead of using a child property this
        #  should use the highest level entry of the config
        self._name = config["name"]

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return ICON

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self.attr
