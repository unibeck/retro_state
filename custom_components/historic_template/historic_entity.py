"""An abstract class for entities."""
import datetime
import functools as ft
import logging
from timeit import default_timer as timer
from typing import Optional, Any, List, Iterable, Dict

from homeassistant.config import DATA_CUSTOMIZE
from homeassistant.const import (
    ATTR_ASSUMED_STATE, ATTR_FRIENDLY_NAME, ATTR_HIDDEN, ATTR_ICON,
    ATTR_UNIT_OF_MEASUREMENT, DEVICE_DEFAULT_NAME, STATE_OFF, STATE_ON,
    STATE_UNAVAILABLE, STATE_UNKNOWN, TEMP_CELSIUS, TEMP_FAHRENHEIT,
    ATTR_ENTITY_PICTURE, ATTR_SUPPORTED_FEATURES, ATTR_DEVICE_CLASS,
    EVENT_STATE_CHANGED)
from homeassistant.core import HomeAssistant, callback, State, Context, EventOrigin
from homeassistant.exceptions import NoEntitySpecifiedError
from homeassistant.util import dt as dt_util
from homeassistant.util import ensure_unique_string, slugify
from homeassistant.util.async_ import run_callback_threadsafe

from custom_components.retro_state.const import EVENT_HISTORIC_STATE_CHANGED

_LOGGER = logging.getLogger(__name__)
SLOW_UPDATE_WARNING = 10


def generate_entity_id(entity_id_format: str, name: Optional[str],
                       current_ids: Optional[List[str]] = None,
                       hass: Optional[HomeAssistant] = None) -> str:
    """Generate a unique entity ID based on given entity IDs or used IDs."""
    if current_ids is None:
        if hass is None:
            raise ValueError("Missing required parameter currentids or hass")
        return run_callback_threadsafe(
            hass.loop, async_generate_entity_id, entity_id_format, name,
            current_ids, hass
        ).result()

    name = (slugify(name) or slugify(DEVICE_DEFAULT_NAME)).lower()

    return ensure_unique_string(
        entity_id_format.format(name), current_ids)


@callback
def async_generate_entity_id(entity_id_format: str, name: Optional[str],
                             current_ids: Optional[Iterable[str]] = None,
                             hass: Optional[HomeAssistant] = None) -> str:
    """Generate a unique entity ID based on given entity IDs or used IDs."""
    if current_ids is None:
        if hass is None:
            raise ValueError("Missing required parameter currentids or hass")

        current_ids = hass.states.async_entity_ids()
    name = (name or DEVICE_DEFAULT_NAME).lower()

    return ensure_unique_string(
        entity_id_format.format(slugify(name)), current_ids)


class HistoricEntity:
    """An abstract class for historic entities."""

    # SAFE TO OVERWRITE
    # The properties and methods here are safe to overwrite when inheriting
    # this class. These may be used to customize the behavior of the entity.
    entity_id = None  # type: str

    # Owning hass instance. Will be set by EntityPlatform
    hass = None  # type: Optional[HomeAssistant]

    # Owning platform instance. Will be set by EntityPlatform
    platform = None

    # If we reported if this entity was slow
    _slow_reported = False

    # Protect for multiple updates
    _update_staged = False

    # Process updates in parallel
    parallel_updates = None

    # Name in the entity registry
    registry_name = None

    # Hold list for functions to call on remove.
    _on_remove = None

    # Context
    _context = None
    _context_set = None

    @property
    def should_poll(self) -> bool:
        """Return True if entity has to be polled for state.

        False if entity pushes its state to HA.
        """
        return True

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return None

    @property
    def name(self) -> Optional[str]:
        """Return the name of the entity."""
        return None

    @property
    def state(self) -> str:
        """Return the state of the entity."""
        return STATE_UNKNOWN

    @property
    def state_attributes(self):
        """Return the state attributes.

        Implemented by component base class.
        """
        return None

    @property
    def device_state_attributes(self):
        """Return device specific state attributes.

        Implemented by platform classes.
        """
        return None

    @property
    def device_info(self):
        """Return device specific attributes.

        Implemented by platform classes.
        """
        return None

    @property
    def device_class(self) -> str:
        """Return the class of this device, from component DEVICE_CLASSES."""
        return None

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return None

    @property
    def last_changed(self):
        """Return the last_changed property, if any."""
        return None

    @property
    def last_updated(self):
        """Return the last_updated property, if any."""
        return None

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return None

    @property
    def entity_picture(self):
        """Return the entity picture to use in the frontend, if any."""
        return None

    @property
    def hidden(self) -> bool:
        """Return True if the entity should be hidden from UIs."""
        return False

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return True

    @property
    def assumed_state(self) -> bool:
        """Return True if unable to access real state of the entity."""
        return False

    @property
    def force_update(self) -> bool:
        """Return True if state updates should be forced.

        If True, a state change will be triggered anytime the state property is
        updated, not just when the value changes.
        """
        return False

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return None

    @property
    def context_recent_time(self):
        """Time that a context is considered recent."""
        return datetime.timedelta(seconds=5)

    # DO NOT OVERWRITE
    # These properties and methods are either managed by Home Assistant or they
    # are used to perform a very specific function. Overwriting these may
    # produce undesirable effects in the entity's operation.

    @callback
    def async_set_context(self, context):
        """Set the context the entity currently operates under."""
        self._context = context
        self._context_set = dt_util.utcnow()

    async def async_update_ha_state(self, force_refresh=False):
        """Update Home Assistant with current state of entity.

        If force_refresh == True will update entity before setting state.

        This method must be run in the event loop.
        """
        if self.hass is None:
            raise RuntimeError("Attribute hass is None for {}".format(self))

        if self.entity_id is None:
            raise NoEntitySpecifiedError(
                "No entity id specified for entity {}".format(self.name))

        # update entity data
        if force_refresh:
            try:
                await self.async_device_update()
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Update for %s fails", self.entity_id)
                return

        self._async_write_ha_state()

    @callback
    def async_write_ha_state(self):
        """Write the state to the state machine."""
        if self.hass is None:
            raise RuntimeError("Attribute hass is None for {}".format(self))

        if self.entity_id is None:
            raise NoEntitySpecifiedError(
                "No entity id specified for entity {}".format(self.name))

        self._async_write_ha_state()

    @callback
    def _async_write_ha_state(self):
        """Write the state to the state machine."""
        start = timer()

        attr = {}
        if not self.available:
            state = STATE_UNAVAILABLE
        else:
            state = self.state

            if state is None:
                state = STATE_UNKNOWN
            else:
                state = str(state)

            attr.update(self.state_attributes or {})
            attr.update(self.device_state_attributes or {})

        unit_of_measurement = self.unit_of_measurement
        if unit_of_measurement is not None:
            attr[ATTR_UNIT_OF_MEASUREMENT] = unit_of_measurement

        name = self.registry_name or self.name
        if name is not None:
            attr[ATTR_FRIENDLY_NAME] = name

        icon = self.icon
        if icon is not None:
            attr[ATTR_ICON] = icon

        entity_picture = self.entity_picture
        if entity_picture is not None:
            attr[ATTR_ENTITY_PICTURE] = entity_picture

        hidden = self.hidden
        if hidden:
            attr[ATTR_HIDDEN] = hidden

        assumed_state = self.assumed_state
        if assumed_state:
            attr[ATTR_ASSUMED_STATE] = assumed_state

        supported_features = self.supported_features
        if supported_features is not None:
            attr[ATTR_SUPPORTED_FEATURES] = supported_features

        device_class = self.device_class
        if device_class is not None:
            attr[ATTR_DEVICE_CLASS] = str(device_class)

        end = timer()

        if end - start > 0.4 and not self._slow_reported:
            self._slow_reported = True
            _LOGGER.warning("Updating state for %s (%s) took %.3f seconds. "
                            "Please report platform to the developers at "
                            "https://goo.gl/Nvioub", self.entity_id,
                            type(self), end - start)

        # Overwrite properties that have been set in the config file.
        if DATA_CUSTOMIZE in self.hass.data:
            attr.update(self.hass.data[DATA_CUSTOMIZE].get(self.entity_id))

        # Convert temperature if we detect one
        try:
            unit_of_measure = attr.get(ATTR_UNIT_OF_MEASUREMENT)
            units = self.hass.config.units
            if (unit_of_measure in (TEMP_CELSIUS, TEMP_FAHRENHEIT) and
                    unit_of_measure != units.temperature_unit):
                prec = len(state) - state.index('.') - 1 if '.' in state else 0
                temp = units.temperature(float(state), unit_of_measure)
                state = str(round(temp) if prec == 0 else round(temp, prec))
                attr[ATTR_UNIT_OF_MEASUREMENT] = units.temperature_unit
        except ValueError:
            # Could not convert state to float
            pass

        if (self._context is not None and
                dt_util.utcnow() - self._context_set >
                self.context_recent_time):
            self._context = None
            self._context_set = None

        self.hass.states.historic_async_set = ft.partial(state_async_set, self.hass.states)
        self.hass.states.historic_async_set(
            self.entity_id, state, attr, self._context,
            self.last_changed, self.last_updated)

    def schedule_update_ha_state(self, force_refresh=False):
        """Schedule an update ha state change task.

        Scheduling the update avoids executor deadlocks.

        Entity state and attributes are read when the update ha state change
        task is executed.
        If state is changed more than once before the ha state change task has
        been executed, the intermediate state transitions will be missed.
        """
        self.hass.add_job(self.async_update_ha_state(force_refresh))

    @callback
    def async_schedule_update_ha_state(self, force_refresh=False):
        """Schedule an update ha state change task.

        This method must be run in the event loop.
        Scheduling the update avoids executor deadlocks.

        Entity state and attributes are read when the update ha state change
        task is executed.
        If state is changed more than once before the ha state change task has
        been executed, the intermediate state transitions will be missed.
        """
        self.hass.async_create_task(self.async_update_ha_state(force_refresh))

    async def async_device_update(self, warning=True):
        """Process 'update' or 'async_update' from entity.

        This method is a coroutine.
        """
        if self._update_staged:
            return
        self._update_staged = True

        # Process update sequential
        if self.parallel_updates:
            await self.parallel_updates.acquire()

        if warning:
            update_warn = self.hass.loop.call_later(
                SLOW_UPDATE_WARNING, _LOGGER.warning,
                "Update of %s is taking over %s seconds", self.entity_id,
                SLOW_UPDATE_WARNING
            )

        try:
            # pylint: disable=no-member
            if hasattr(self, 'async_update'):
                await self.async_update()
            elif hasattr(self, 'update'):
                await self.hass.async_add_executor_job(self.update)
        finally:
            self._update_staged = False
            if warning:
                update_warn.cancel()
            if self.parallel_updates:
                self.parallel_updates.release()

    @callback
    def async_on_remove(self, func):
        """Add a function to call when entity removed."""
        if self._on_remove is None:
            self._on_remove = []
        self._on_remove.append(func)

    async def async_remove(self):
        """Remove entity from Home Assistant."""
        await self.async_will_remove_from_hass()

        if self._on_remove is not None:
            while self._on_remove:
                self._on_remove.pop()()

        self.hass.states.async_remove(self.entity_id)

    @callback
    def async_registry_updated(self, old, new):
        """Handle entity registry update."""
        self.registry_name = new.name

        if new.entity_id == self.entity_id:
            self.async_schedule_update_ha_state()
            return

        async def readd():
            """Remove and add entity again."""
            await self.async_remove()
            await self.platform.async_add_entities([self])

        self.hass.async_create_task(readd())

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""

    def __eq__(self, other):
        """Return the comparison."""
        if not isinstance(other, self.__class__):
            return False

        # Can only decide equality if both have a unique id
        if self.unique_id is None or other.unique_id is None:
            return False

        # Ensure they belong to the same platform
        if self.platform is not None or other.platform is not None:
            if self.platform is None or other.platform is None:
                return False

            if self.platform.platform != other.platform.platform:
                return False

        return self.unique_id == other.unique_id

    def __repr__(self):
        """Return the representation."""
        return "<Entity {}: {}>".format(self.name, self.state)


def state_async_set(self, entity_id: str, new_state: Any,
                    attributes: Optional[Dict] = None,
                    context: Optional[Context] = None,
                    last_changed: Optional[datetime.datetime] = None,
                    last_updated: Optional[datetime.datetime] = None) -> None:
    """Set the state of an entity, add entity if it does not exist.

    Attributes is an optional dict to specify attributes of this state.

    If you just update the attributes and not the state, last changed will
    not be affected.

    This method must be run in the event loop.
    """
    entity_id = entity_id.lower()
    new_state = str(new_state)
    attributes = attributes or {}
    old_state = self._states.get(entity_id)

    if old_state is None:
        last_changed = None
    else:
        last_changed = last_changed

    if context is None:
        context = Context()

    state = State(entity_id, new_state, attributes,
                  last_changed, last_updated, context)

    # Default to the base state changed event
    event = EVENT_STATE_CHANGED

    if old_state and old_state.state:
        if old_state.last_updated and last_updated and old_state.last_updated > last_updated:
            _LOGGER.debug("last_updated of newer state is less than the last_updated of the current state [%s < %s]",
                          last_updated, old_state.last_updated)
            event = EVENT_HISTORIC_STATE_CHANGED
        elif old_state.last_changed and last_changed and old_state.last_changed > last_changed:
            _LOGGER.debug("last_changed of newer state is less than the last_changed of the current state [%s < %s]",
                          last_changed, old_state.last_changed)
            event = EVENT_HISTORIC_STATE_CHANGED
        else:
            self._states[entity_id] = state
    else:
        self._states[entity_id] = state

    self._bus.async_fire(event, {
        'entity_id': entity_id,
        'old_state': old_state,
        'new_state': state,
    }, EventOrigin.local, context)


class ToggleEntity(HistoricEntity):
    """An abstract class for entities that can be turned on and off."""

    @property
    def state(self) -> str:
        """Return the state."""
        return STATE_ON if self.is_on else STATE_OFF

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        raise NotImplementedError()

    def turn_on(self, **kwargs) -> None:
        """Turn the entity on."""
        raise NotImplementedError()

    def async_turn_on(self, **kwargs):
        """Turn the entity on.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(
            ft.partial(self.turn_on, **kwargs))

    def turn_off(self, **kwargs) -> None:
        """Turn the entity off."""
        raise NotImplementedError()

    def async_turn_off(self, **kwargs):
        """Turn the entity off.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(
            ft.partial(self.turn_off, **kwargs))

    def toggle(self, **kwargs) -> None:
        """Toggle the entity."""
        if self.is_on:
            self.turn_off(**kwargs)
        else:
            self.turn_on(**kwargs)

    def async_toggle(self, **kwargs):
        """Toggle the entity.

        This method must be run in the event loop and returns a coroutine.
        """
        if self.is_on:
            return self.async_turn_off(**kwargs)
        return self.async_turn_on(**kwargs)
