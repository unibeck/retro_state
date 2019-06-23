"""Integration with InfluxDB component from base Home Assistant.

06/03/19
# Updated event_to_json inner function to use a state's last_updated value
# instead of the event's time_fired value
"""

import logging
import time
from threading import Thread

import math
import requests
from homeassistant.components.influxdb import InfluxThread, CONF_DB_NAME, TIMEOUT, CONF_TAGS, \
    CONF_TAGS_ATTRIBUTES, CONF_DEFAULT_MEASUREMENT, CONF_OVERRIDE_MEASUREMENT, CONF_COMPONENT_CONFIG, \
    CONF_COMPONENT_CONFIG_DOMAIN, CONF_COMPONENT_CONFIG_GLOB, CONF_RETRY_COUNT, RETRY_INTERVAL, RE_DIGIT_TAIL, \
    RE_DECIMAL, DOMAIN, CONFIG_SCHEMA
from homeassistant.const import (
    EVENT_HOMEASSISTANT_STOP, CONF_VERIFY_SSL, CONF_HOST, CONF_PORT, CONF_USERNAME, CONF_PASSWORD, CONF_SSL,
    CONF_INCLUDE,
    CONF_EXCLUDE, CONF_ENTITIES, CONF_DOMAINS, STATE_UNKNOWN, STATE_UNAVAILABLE)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import state as state_helper, event as event_helper
from homeassistant.helpers.entity_values import EntityValues
from homeassistant.helpers.typing import ConfigType

from .const import EVENT_HISTORIC_STATE_CHANGED, DOMAIN as RETRO_STATE_DOMAIN

_LOGGER = logging.getLogger(__name__)


def configure(hass: HomeAssistant, config: ConfigType):
    if DOMAIN in config:
        thread = Thread(target=_async_setup, args=(hass, config, ))
        thread.start()
    else:
        _LOGGER.warning("You must configure the base HA [%s] in order to use retro_state's [%s] integration.",
                        DOMAIN, DOMAIN)


def _async_setup(hass: HomeAssistant, config: ConfigType):
    instance = None
    wait_attempts = 0

    # Wait up to 60 seconds (5 sec sleep * 12 attempts) for influxdb component to start
    while wait_attempts < 12 and not instance:
        wait_attempts += 1
        try:
            instance = hass.data[DOMAIN]
        except KeyError:
            _LOGGER.info("Waiting for the base HA [%s] component to start. Sleeping for five seconds...",
                         DOMAIN)
            time.sleep(5)
        else:
            # Stop the base HA influxdb component
            instance.queue.put(None)
            instance.join()
            hass.data[DOMAIN] = None
            _LOGGER.info("Stopped the base HA [%s] component", DOMAIN)

    if not instance:
        _LOGGER.warning("The base HA [%s] component was not started after 60 seconds", DOMAIN)

    # Process the config to fill in defaults
    processed_config = CONFIG_SCHEMA(config)

    # Run the modified setup function
    _LOGGER.info("Starting %s's [%s] integration", RETRO_STATE_DOMAIN, DOMAIN)
    _setup(hass, processed_config)
    return


def _setup(hass, config):
    """Set up the InfluxDB component."""
    from influxdb import InfluxDBClient, exceptions

    conf = config[DOMAIN]

    kwargs = {
        'database': conf[CONF_DB_NAME],
        'verify_ssl': conf[CONF_VERIFY_SSL],
        'timeout': TIMEOUT
    }

    if CONF_HOST in conf:
        kwargs['host'] = conf[CONF_HOST]

    if CONF_PORT in conf:
        kwargs['port'] = conf[CONF_PORT]

    if CONF_USERNAME in conf:
        kwargs['username'] = conf[CONF_USERNAME]

    if CONF_PASSWORD in conf:
        kwargs['password'] = conf[CONF_PASSWORD]

    if CONF_SSL in conf:
        kwargs['ssl'] = conf[CONF_SSL]

    include = conf.get(CONF_INCLUDE, {})
    exclude = conf.get(CONF_EXCLUDE, {})
    whitelist_e = set(include.get(CONF_ENTITIES, []))
    whitelist_d = set(include.get(CONF_DOMAINS, []))
    blacklist_e = set(exclude.get(CONF_ENTITIES, []))
    blacklist_d = set(exclude.get(CONF_DOMAINS, []))
    tags = conf.get(CONF_TAGS)
    tags_attributes = conf.get(CONF_TAGS_ATTRIBUTES)
    default_measurement = conf.get(CONF_DEFAULT_MEASUREMENT)
    override_measurement = conf.get(CONF_OVERRIDE_MEASUREMENT)
    component_config = EntityValues(
        conf[CONF_COMPONENT_CONFIG],
        conf[CONF_COMPONENT_CONFIG_DOMAIN],
        conf[CONF_COMPONENT_CONFIG_GLOB])
    max_tries = conf.get(CONF_RETRY_COUNT)

    try:
        influx = InfluxDBClient(**kwargs)
        influx.write_points([])
    except (exceptions.InfluxDBClientError,
            requests.exceptions.ConnectionError) as exc:
        _LOGGER.warning(
            "Database host is not accessible due to '%s', please "
            "check your entries in the configuration file (host, "
            "port, etc.) and verify that the database exists and is "
            "READ/WRITE. Retrying again in %s seconds.", exc, RETRY_INTERVAL
        )
        event_helper.call_later(
            hass, RETRY_INTERVAL, lambda _: _setup(hass, config)
        )
        return True

    def event_to_json(event):
        """Add an event to the outgoing Influx list."""
        state = event.data.get('new_state')
        if state is None or state.state in (
                STATE_UNKNOWN, '', STATE_UNAVAILABLE) or \
                state.entity_id in blacklist_e or state.domain in blacklist_d:
            return

        try:
            if ((whitelist_e or whitelist_d)
                    and state.entity_id not in whitelist_e
                    and state.domain not in whitelist_d):
                return

            _include_state = _include_value = False

            _state_as_value = float(state.state)
            _include_value = True
        except ValueError:
            try:
                _state_as_value = float(state_helper.state_as_number(state))
                _include_state = _include_value = True
            except ValueError:
                _include_state = True

        include_uom = True
        measurement = component_config.get(state.entity_id).get(
            CONF_OVERRIDE_MEASUREMENT)
        if measurement in (None, ''):
            if override_measurement:
                measurement = override_measurement
            else:
                measurement = state.attributes.get('unit_of_measurement')
                if measurement in (None, ''):
                    if default_measurement:
                        measurement = default_measurement
                    else:
                        measurement = state.entity_id
                else:
                    include_uom = False

        if event.event_type == EVENT_HISTORIC_STATE_CHANGED:
            event_time = state.last_updated
        else:
            event_time = event.time_fired

        json = {
            'measurement': measurement,
            'tags': {
                'domain': state.domain,
                'entity_id': state.object_id,
            },
            'time': event_time,
            'fields': {}
        }
        if _include_state:
            json['fields']['state'] = state.state
        if _include_value:
            json['fields']['value'] = _state_as_value

        for key, value in state.attributes.items():
            if key in tags_attributes:
                json['tags'][key] = value
            elif key != 'unit_of_measurement' or include_uom:
                # If the key is already in fields
                if key in json['fields']:
                    key = key + "_"
                # Prevent column data errors in influxDB.
                # For each value we try to cast it as float
                # But if we can not do it we store the value
                # as string add "_str" postfix to the field key
                try:
                    json['fields'][key] = float(value)
                except (ValueError, TypeError):
                    new_key = "{}_str".format(key)
                    new_value = str(value)
                    json['fields'][new_key] = new_value

                    if RE_DIGIT_TAIL.match(new_value):
                        json['fields'][key] = float(
                            RE_DECIMAL.sub('', new_value))

                # Infinity and NaN are not valid floats in InfluxDB
                try:
                    if not math.isfinite(json['fields'][key]):
                        del json['fields'][key]
                except (KeyError, TypeError):
                    pass

        json['tags'].update(tags)

        return json

    instance = hass.data[DOMAIN] = InfluxThread(
        hass, influx, event_to_json, max_tries)
    instance.start()

    def shutdown(event):
        """Shut down the thread."""
        instance.queue.put(None)
        instance.join()
        influx.close()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, shutdown)

    return True
