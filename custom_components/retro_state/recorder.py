"""Integration with Recorder component from base Home Assistant."""

import concurrent.futures
import logging
import time
from datetime import timedelta
from threading import Thread

import homeassistant.util.dt as dt_util
from homeassistant.components import persistent_notification
from homeassistant.components.recorder import CONNECT_RETRY_WAIT, PurgeTask, migration, purge
from homeassistant.components.recorder import Recorder, async_setup as recorder_async_setup
from homeassistant.components.recorder.models import States, Events
from homeassistant.components.recorder.util import session_scope
from homeassistant.const import (
    ATTR_ENTITY_ID, EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP, EVENT_STATE_CHANGED,
    EVENT_TIME_CHANGED)
from homeassistant.core import CoreState, callback, HomeAssistant
from sqlalchemy import exc

from .const import EVENT_HISTORIC_STATE_CHANGED

_LOGGER = logging.getLogger(__name__)


def setup(hass: HomeAssistant, config):
    thread = Thread(target=_async_setup, args=(hass, config, ))
    thread.start()


def _async_setup(hass: HomeAssistant, config):
    # Stop the base HA recorder component.
    recorder = hass.data["recorder_instance"]
    recorder.queue.put(None)
    recorder.join()
    hass.data["recorder_instance"] = None

    # Overwrite the run method of the Recorder class. Then set up the
    # component again
    Recorder.run = _run
    hass.async_create_task(recorder_async_setup(hass, config["recorder"]))
    return


def _run(self):
    """Start processing events to save."""
    tries = 1
    connected = False

    while not connected and tries <= 10:
        if tries != 1:
            time.sleep(CONNECT_RETRY_WAIT)
        try:
            self._setup_connection()
            migration.migrate_schema(self)
            self._setup_run()
            connected = True
            _LOGGER.debug("Connected to recorder database")
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.error("Error during connection setup: %s (retrying "
                          "in %s seconds)", err, CONNECT_RETRY_WAIT)
            tries += 1

    if not connected:
        @callback
        def connection_failed():
            """Connect failed tasks."""
            self.async_db_ready.set_result(False)
            persistent_notification.async_create(
                self.hass,
                "The recorder could not start, please check the log",
                "Recorder")

        self.hass.add_job(connection_failed)
        return

    shutdown_task = object()
    hass_started = concurrent.futures.Future()

    @callback
    def register():
        """Post connection initialize."""
        self.async_db_ready.set_result(True)

        def shutdown(event):
            """Shut down the Recorder."""
            if not hass_started.done():
                hass_started.set_result(shutdown_task)
            self.queue.put(None)
            self.join()

        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, shutdown)

        if self.hass.state == CoreState.running:
            hass_started.set_result(None)
        else:
            @callback
            def notify_hass_started(event):
                """Notify that hass has started."""
                hass_started.set_result(None)

            self.hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_START, notify_hass_started)

    self.hass.add_job(register)
    result = hass_started.result()

    # If shutdown happened before Home Assistant finished starting
    if result is shutdown_task:
        return

    # Start periodic purge
    if self.keep_days and self.purge_interval:
        @callback
        def async_purge(now):
            """Trigger the purge and schedule the next run."""
            self.queue.put(
                PurgeTask(self.keep_days, repack=False))
            self.hass.helpers.event.async_track_point_in_time(
                async_purge, now + timedelta(days=self.purge_interval))

        earliest = dt_util.utcnow() + timedelta(minutes=30)
        run_time = latest = dt_util.utcnow() + \
                       timedelta(days=self.purge_interval)
        with session_scope(session=self.get_session()) as session:
            event = session.query(Events).first()
            if event is not None:
                session.expunge(event)
                run_time = dt_util.as_utc(event.time_fired) + timedelta(
                    days=self.keep_days+self.purge_interval)
        run_time = min(latest, max(run_time, earliest))

        self.hass.helpers.event.track_point_in_time(async_purge, run_time)

    while True:
        event = self.queue.get()

        if event is None:
            self._close_run()
            self._close_connection()
            self.queue.task_done()
            return
        if isinstance(event, PurgeTask):
            purge.purge_old_data(self, event.keep_days, event.repack)
            self.queue.task_done()
            continue
        elif event.event_type == EVENT_TIME_CHANGED:
            self.queue.task_done()
            continue
        elif event.event_type in self.exclude_t:
            self.queue.task_done()
            continue

        entity_id = event.data.get(ATTR_ENTITY_ID)
        if entity_id is not None:
            if not self.entity_filter(entity_id):
                self.queue.task_done()
                continue

        tries = 1
        updated = False
        while not updated and tries <= 10:
            if tries != 1:
                time.sleep(CONNECT_RETRY_WAIT)
            try:
                with session_scope(session=self.get_session()) as session:
                    try:
                        dbevent = Events.from_event(event)
                        session.add(dbevent)
                        session.flush()
                    except (TypeError, ValueError):
                        _LOGGER.warning(
                            "Event is not JSON serializable: %s", event)

                    if event.event_type == EVENT_STATE_CHANGED or \
                            event.event_type == EVENT_HISTORIC_STATE_CHANGED:
                        try:
                            dbstate = States.from_event(event)
                            dbstate.event_id = dbevent.event_id
                            session.add(dbstate)
                        except (TypeError, ValueError):
                            _LOGGER.warning(
                                "State is not JSON serializable: %s",
                                event.data.get('new_state'))

                updated = True

            except exc.OperationalError as err:
                _LOGGER.error("Error in database connectivity: %s. "
                              "(retrying in %s seconds)", err,
                              CONNECT_RETRY_WAIT)
                tries += 1

            except exc.SQLAlchemyError:
                updated = True
                _LOGGER.exception("Error saving event: %s", event)

        if not updated:
            _LOGGER.error("Error in database update. Could not save "
                          "after %d tries. Giving up", tries)

        self.queue.task_done()
