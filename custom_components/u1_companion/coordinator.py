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

from .api import CannotConnect, InvalidAuth, U1Api, Unsupported, parse_heads
from .const import DOMAIN, POLL_SECONDS, STORAGE_VERSION
from . import model

_LOGGER = logging.getLogger(__name__)


class U1Coordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry):
        super().__init__(hass, _LOGGER, name=DOMAIN, config_entry=entry,
                         update_interval=timedelta(seconds=POLL_SECONDS))
        self.entry = entry
        self.store = Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}")
        self.demo = entry.data.get("demo", False)
        self.api = None if self.demo else U1Api(async_get_clientsession(hass), entry.data["host"],
                         entry.data["port"], entry.data.get("api_key", ""))
        self.lock = asyncio.Lock()
        self.catalog = None
        self.state = None
        self.connected = False
        self.error = "unknown"
        self.last_success = None
        self.current_hours = None
        self.heads = parse_heads({})
        self.current_swaps = None
        self.head_error = "unknown"
        self.accept_head_reset = False

    def today(self):
        return dt_util.now().date().isoformat()

    async def async_load(self):
        def read_catalog():
            return json.loads(Path(__file__).with_name("catalog.json").read_text(encoding="utf-8"))

        self.catalog = await self.hass.async_add_executor_job(read_catalog)
        stored = await self.store.async_load()
        self.state = model.validate(stored, self.catalog) if stored is not None else model.fresh(self.catalog)
        if stored is None and not self.demo:
            self.state["machine"]["name"] = self.entry.data.get("name", "Mon U1")
            start = self.entry.data.get("start_date")
            if start:
                self.state = model.reference_date(self.state, start, self.today(), self.catalog)
            await self.store.async_save(self.state)
        elif stored is not None and self.entry.data.get("name"):
            self.state["machine"]["name"] = self.entry.data["name"]
        if self.demo:
            self.state["demo"] = True
            if stored is None:
                self.state["machine"].update(name="U1 SIMULÉE", hours=1200.0, swaps=42000, hoursSource="demo")
                for task, age in zip(self.state["tasks"], [3, 28, 50, 100, 5, 180, 10]):
                    task["calendarBaseDate"] = (dt_util.now().date() - timedelta(days=age)).isoformat()
                await self.store.async_save(self.state)
        # Never reuse an old successful reading as a current measurement after restart.
        self.current_hours = None

    def build_snapshot(self):
        view = deepcopy(self.state)
        if view["machine"].get("hoursSource") == "moonraker-history":
            view["machine"]["hours"] = self.current_hours
        if view["machine"].get("swapsSource") == "u1-extruders":
            view["machine"]["swaps"] = self.current_swaps
        return {**model.snapshot(view, self.today()), "hours": view["machine"]["hours"],
                "swaps": view["machine"]["swaps"], "heads": deepcopy(self.heads),
                "head_error": self.head_error,
                "swaps_source": view["machine"].get("swapsSource", "manual" if view["machine"]["swaps"] is not None else "unknown"),
                "hours_source": view["machine"].get("hoursSource", "unknown"),
                "demo": self.demo, "connected": self.connected, "connection_error": self.error,
                "last_success": self.last_success, "catalog_version": self.catalog["version"]}

    async def _async_update_data(self):
        if self.demo:
            self.connected = False
            self.error = "demo_no_printer"
            return self.build_snapshot()
        try:
            hours = await self.api.async_hours()
            error = None
        except InvalidAuth:
            hours, error = None, "invalid_auth"
        except Unsupported:
            hours, error = None, "history_missing"
        except CannotConnect:
            hours, error = None, "cannot_connect"
        try:
            heads = await self.api.async_heads()
            head_error = "ok"
        except InvalidAuth:
            heads, head_error = parse_heads({}), "invalid_auth"
        except Unsupported:
            heads, head_error = parse_heads({}), "heads_missing"
        except CannotConnect:
            heads, head_error = parse_heads({}), "cannot_connect"
        async with self.lock:
            self.heads = heads
            self.head_error = head_error
            self.current_swaps = None
            if head_error == "ok":
                try:
                    next_state = model.apply_heads(self.state, heads, self.accept_head_reset)
                except ValueError as err:
                    self.head_error = "head_counter_reset" if str(err) == "head_counter_reset" else "heads_missing"
                else:
                    try:
                        if next_state != self.state:
                            await self.store.async_save(model.validate(next_state, self.catalog))
                        self.state = next_state
                        self.current_swaps = self.state["machine"]["swaps"]
                        self.accept_head_reset = False
                    except OSError as err:
                        raise UpdateFailed("Toolhead counters could not be saved") from err
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
            if state["machine"].get("swapsSource") == "u1-extruders" and self.current_swaps is None:
                state["machine"]["swaps"] = None
            return model.complete(state, task_id, checked, note, completed_day,
                                  self.today(), self.catalog)
        await self.async_change(change)

    async def async_reference(self, value):
        await self.async_change(lambda state: model.reference_date(state, value, self.today(), self.catalog))

    async def async_import(self, state):
        """Import only the maintenance state, never a bridge host or credentials."""
        if state.get("demo") and not self.demo:
            raise ValueError("Simulated records cannot be imported into a real printer")
        next_state = deepcopy(model.validate(state, self.catalog))
        if self.demo:
            next_state["demo"] = True
        next_state["connection"] = {"url": "", "enabled": True,
                                    "status": "unknown", "lastSuccess": None}
        # A separate pre-import backup survives later updates, until integration removal.
        backup = Store(self.hass, STORAGE_VERSION, f"{DOMAIN}.{self.entry.entry_id}.before_import")
        async with self.lock:
            await backup.async_save(self.state)
            await self.store.async_save(next_state)
            self.state = next_state
            self.async_set_updated_data(self.build_snapshot())
