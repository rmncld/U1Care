"""Local persistent maintenance plus read-only printer polling."""

import asyncio
from copy import deepcopy
from datetime import timedelta
import json
import logging
from pathlib import Path

from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import CannotConnect, InvalidAuth, U1Api, Unsupported
from .const import DOMAIN, POLL_SECONDS, STORAGE_VERSION
from . import model

_LOGGER = logging.getLogger(__name__)


class U1Coordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry):
        super().__init__(hass, _LOGGER, name=DOMAIN, config_entry=entry,
                         update_interval=timedelta(seconds=POLL_SECONDS))
        self.entry = entry
        self.store = Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}")
        self.api = U1Api(async_get_clientsession(hass), entry.data["host"],
                         entry.data["port"], entry.data.get("api_key", ""))
        self.lock = asyncio.Lock()
        self.catalog = None
        self.state = None
        self.connected = False
        self.error = "unknown"
        self.last_success = None
        self.current_hours = None

    def today(self):
        return dt_util.now().date().isoformat()

    async def async_load(self):
        def read_catalog():
            return json.loads(Path(__file__).with_name("catalog.json").read_text(encoding="utf-8"))

        self.catalog = await self.hass.async_add_executor_job(read_catalog)
        stored = await self.store.async_load()
        self.state = model.validate(stored, self.catalog) if stored is not None else model.fresh(self.catalog)
        # Never reuse an old successful reading as a current measurement after restart.
        self.current_hours = None

    def build_snapshot(self):
        view = deepcopy(self.state)
        if view["machine"].get("hoursSource") == "moonraker-history":
            view["machine"]["hours"] = self.current_hours
        return {**model.snapshot(view, self.today()), "hours": view["machine"]["hours"],
                "hours_source": view["machine"].get("hoursSource", "unknown"),
                "connected": self.connected, "connection_error": self.error,
                "last_success": self.last_success, "catalog_version": self.catalog["version"]}

    async def _async_update_data(self):
        try:
            hours = await self.api.async_hours()
            error = None
        except InvalidAuth:
            hours, error = None, "invalid_auth"
        except Unsupported:
            hours, error = None, "history_missing"
        except CannotConnect:
            hours, error = None, "cannot_connect"
        async with self.lock:
            if error:
                self.connected = False
                self.error = error
                self.current_hours = None
            else:
                self.connected = True
                self.error = "ok"
                try:
                    next_state = model.apply_history(self.state, hours)
                    changed = next_state != self.state
                    if changed:
                        await self.store.async_save(model.validate(next_state, self.catalog))
                    self.state = next_state
                    self.current_hours = hours
                    self.last_success = dt_util.utcnow().isoformat()
                except ValueError:
                    self.current_hours = None
                    self.error = "history_reset"
                except OSError as err:
                    raise UpdateFailed("Maintenance storage could not be saved") from err
            return self.build_snapshot()

    async def async_change(self, operation):
        """All UI changes are serialized with polling and saved before display."""
        async with self.lock:
            next_state = operation(deepcopy(self.state))
            model.validate(next_state, self.catalog)
            await self.store.async_save(next_state)
            self.state = next_state
            self.async_set_updated_data(self.build_snapshot())

    async def async_complete(self, task_id, checked, note, completed_day):
        def change(state):
            # A stale historical reading is not a current maintenance counter.
            if state["machine"].get("hoursSource") == "moonraker-history" and self.current_hours is None:
                state["machine"]["hours"] = None
            return model.complete(state, task_id, checked, note, completed_day,
                                  self.today(), self.catalog)
        await self.async_change(change)

    async def async_reference(self, value):
        await self.async_change(lambda state: model.reference_date(state, value, self.today(), self.catalog))

    async def async_import(self, state):
        """Import only the maintenance state, never a bridge host or credentials."""
        next_state = deepcopy(model.validate(state, self.catalog))
        next_state["connection"] = {"url": "", "enabled": True,
                                    "status": "unknown", "lastSuccess": None}
        # A separate pre-import backup survives later updates, until integration removal.
        backup = Store(self.hass, STORAGE_VERSION, f"{DOMAIN}.{self.entry.entry_id}.before_import")
        async with self.lock:
            await backup.async_save(self.state)
            await self.store.async_save(next_state)
            self.state = next_state
            self.async_set_updated_data(self.build_snapshot())
