"""IP-only setup and guided local maintenance forms."""

from copy import deepcopy
import json

try:
    import probatio as vol
except ImportError:  # Home Assistant 2026.8 uses voluptuous.
    import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import selector
from homeassistant.util import dt as dt_util

from .api import CannotConnect, InvalidAuth, Unsupported, async_discover, normalize_host
from .const import DOMAIN
from . import model


class U1ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 2

    def __init__(self):
        self._host = None
        self._reconfigure = None
        self._details = {}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return U1OptionsFlow()

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                self._host = normalize_host(user_input["host"])
            except (ValueError, KeyError):
                errors["host"] = "invalid_host"
            else:
                current_name = self._reconfigure.data.get("name", "Mon U1") if self._reconfigure else "Mon U1"
                name = user_input.get("name", self._details.get("name", current_name)).strip()
                start = user_input.get("start_date", self._details.get("start_date"))
                if not name or len(name) > 80:
                    errors["name"] = "invalid_name"
                if start:
                    try:
                        if model.valid_day(start) > dt_util.now().date():
                            raise ValueError("invalid_date")
                    except (ValueError, TypeError):
                        errors["start_date"] = "invalid_date"
                self._details = {"name": name, **({"start_date": start} if start else {})}
                if errors:
                    return self.async_show_form(step_id="user", data_schema=self._user_schema(), errors=errors)
                for entry in self._async_current_entries():
                    if entry.data.get("host") == self._host and entry is not self._reconfigure:
                        return self.async_abort(reason="already_configured")
                return await self._try_connect()
        return self.async_show_form(step_id="user", data_schema=self._user_schema(), errors=errors)

    def _user_schema(self):
        data = {**(self._reconfigure.data if self._reconfigure else {}), **self._details}
        start_field = (vol.Optional("start_date", default=data["start_date"])
                       if data.get("start_date") else vol.Optional("start_date"))
        schema = {
            vol.Required("host", default=self._host or data.get("host", "")): str,
            vol.Required("name", default=data.get("name", "Mon U1")): str}
        if self._reconfigure is None:
            schema[start_field] = selector.DateSelector()
        return vol.Schema(schema)

    async def _try_connect(self, api_key=""):
        try:
            found = await async_discover(async_get_clientsession(self.hass), self._host, api_key)
        except InvalidAuth:
            return self.async_show_form(step_id="auth", data_schema=self._auth_schema(),
                                        errors={"base": "invalid_auth"} if api_key else {})
        except Unsupported:
            return self.async_show_form(step_id="user", data_schema=self._user_schema(), errors={"base": "unsupported"})
        except CannotConnect:
            return self.async_show_form(step_id="user", data_schema=self._user_schema(), errors={"base": "cannot_connect"})
        data = {**(self._reconfigure.data if self._reconfigure else {}), **self._details,
                "host": self._host, "port": found["port"], "api_key": api_key,
                "moonraker_version": found["moonraker_version"]}
        if self._reconfigure:
            return self.async_update_reload_and_abort(self._reconfigure, data=data,
                                                      title=data.get("name", "Mon U1"),
                                                      reason="reconfigure_successful")
        # No fabricated serial number or mutable IP-based unique_id.
        # Entity IDs are based on HA's persistent entry ID.
        return self.async_create_entry(title=data.get("name", "Mon U1"), data=data)

    @staticmethod
    def _auth_schema():
        return vol.Schema({vol.Required("api_key"): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD))})

    async def async_step_auth(self, user_input=None):
        if user_input:
            return await self._try_connect(user_input["api_key"].strip())
        return self.async_show_form(step_id="auth", data_schema=self._auth_schema())

    async def async_step_reconfigure(self, user_input=None):
        self._reconfigure = self._get_reconfigure_entry()
        if self._reconfigure.data.get("demo"):
            return self.async_abort(reason="demo_separate")
        return await self.async_step_user(user_input)


class U1OptionsFlow(config_entries.OptionsFlow):
    """Settings are native forms, not YAML and not automatic maintenance resets."""

    def __init__(self):
        self._task_id = None

    @property
    def coordinator(self):
        return self.config_entry.runtime_data

    def _finish(self):
        return self.async_create_entry(title="", data=dict(self.config_entry.options))

    async def async_step_init(self, user_input=None):
        return self.async_show_menu(step_id="init", menu_options=[
            "maintenance", "reference", "signal", "counters", "resume", "import_backup", "dashboard"])

    async def async_step_dashboard(self, user_input=None):
        if user_input is not None:
            return self._finish()
        from .dashboard_config import async_dashboard_config
        path = self.config_entry.options.get("dashboard_path") or f"u1-care-{self.config_entry.entry_id[:8].lower()}"
        config = await async_dashboard_config(self.hass, self.config_entry, path)
        return self.async_show_form(step_id="dashboard", data_schema=vol.Schema({
            vol.Optional("dashboard_json", default=json.dumps(config, ensure_ascii=False, indent=2)):
                selector.TextSelector(selector.TextSelectorConfig(multiline=True))}),
            description_placeholders={"path": path})

    async def async_step_maintenance(self, user_input=None):
        if user_input:
            self._task_id = user_input["task_id"]
            return await self.async_step_complete()
        tasks = self.coordinator.catalog["tasks"]
        return self.async_show_form(step_id="maintenance", data_schema=vol.Schema({
            vol.Required("task_id"): selector.SelectSelector(selector.SelectSelectorConfig(
                options=[{"value": t["id"], "label": t["title"]} for t in tasks],
                mode=selector.SelectSelectorMode.DROPDOWN))}))

    async def async_step_complete(self, user_input=None):
        task = next(t for t in self.coordinator.catalog["tasks"] if t["id"] == self._task_id)
        errors = {}
        if user_input:
            checked = [user_input.get(f"step_{i+1}", False) for i in range(len(task["steps"]))]
            try:
                await self.coordinator.async_complete(self._task_id, checked,
                    user_input.get("note", ""), user_input["completed_day"])
            except (ValueError, TypeError) as err:
                errors["base"] = str(err) if str(err) in ("check_all_steps", "invalid_date", "invalid_note") else "invalid_date"
            except OSError:
                errors["base"] = "save_failed"
            else:
                return self._finish()
        schema = {vol.Required("completed_day", default=self.coordinator.today()): selector.DateSelector()}
        schema.update({vol.Required(f"step_{i+1}", default=False): bool for i in range(len(task["steps"]))})
        schema[vol.Optional("note", default="")] = selector.TextSelector(selector.TextSelectorConfig(multiline=True))
        procedure = "\n\n".join(f"{i+1}. {text}" for i, text in enumerate(task["steps"]))
        return self.async_show_form(step_id="complete", data_schema=vol.Schema(schema), errors=errors,
            description_placeholders={"task": task["title"], "procedure": procedure, "source": task["source"]})

    async def async_step_reference(self, user_input=None):
        errors = {}
        if user_input:
            try:
                await self.coordinator.async_reference(user_input["start_date"])
            except (ValueError, TypeError):
                errors["base"] = "invalid_date"
            except OSError:
                errors["base"] = "save_failed"
            else:
                return self._finish()
        current = self.coordinator.state["machine"].get("startDate")
        field = vol.Required("start_date", default=current) if current else vol.Required("start_date")
        return self.async_show_form(step_id="reference", data_schema=vol.Schema({
            field: selector.DateSelector()}), errors=errors)

    async def async_step_signal(self, user_input=None):
        errors = {}
        if user_input is not None:
            def change(state):
                next(t for t in state["tasks"] if t["id"] == "xyz-calibration")["conditionActive"] = user_input["active"]
                return state
            try:
                await self.coordinator.async_change(change)
            except OSError:
                errors["base"] = "save_failed"
            else:
                return self._finish()
        task = next(t for t in self.coordinator.state["tasks"] if t["id"] == "xyz-calibration")
        return self.async_show_form(step_id="signal", data_schema=vol.Schema({
            vol.Required("active", default=task["conditionActive"]): bool}), errors=errors)

    async def async_step_counters(self, user_input=None):
        errors = {}
        if user_input:
            def change(state):
                if not any(user_input.get(k) is not None for k in ("hours", "swaps")):
                    raise ValueError("no_counter")
                for key in ("hours", "swaps"):
                    value = user_input.get(key)
                    if value is None:
                        continue
                    model.number(value, integer=key == "swaps")
                    old = state["machine"].get(key)
                    if old is not None and value < old:
                        raise ValueError("counter_decreased")
                    state["machine"][key] = value
                    if key == "swaps":
                        state["machine"]["swapsSource"] = "manual"
                    if key == "hours":
                        state["machine"]["hoursSource"] = "manual"
                        state["connection"]["enabled"] = False
                return state
            try:
                await self.coordinator.async_change(change)
            except (ValueError, TypeError):
                errors["base"] = "invalid_counter"
            except OSError:
                errors["base"] = "save_failed"
            else:
                return self._finish()
        return self.async_show_form(step_id="counters", data_schema=vol.Schema({
            vol.Optional("swaps"): selector.NumberSelector(selector.NumberSelectorConfig(
                min=0, max=1e9, step=1, mode=selector.NumberSelectorMode.BOX)),
            vol.Optional("hours"): selector.NumberSelector(selector.NumberSelectorConfig(
                min=0, max=1e9, step=0.01, mode=selector.NumberSelectorMode.BOX))}), errors=errors)

    async def async_step_resume(self, user_input=None):
        errors = {}
        if user_input:
            if user_input.get("confirm") is not True:
                errors["base"] = "confirm_required"
            else:
                def change(state):
                    state["connection"]["enabled"] = True
                    if state["machine"].get("swapsSource") == "manual":
                        state["machine"].pop("swapsSource", None)
                        if "toolheadCounters" in state:
                            state["previousToolheadCounters"] = state.pop("toolheadCounters")
                    # Explicitly start a new history domain if a reset was detected.
                    if self.coordinator.error == "history_reset":
                        state["connection"]["previousHistoryHours"] = state["connection"].pop("lastReadingHours", None)
                        for task in state["tasks"]:
                            if task.get("lastHours") is not None:
                                task["previousHistoryLastHours"] = task["lastHours"]
                                task["lastHours"] = None
                    return state
                try:
                    await self.coordinator.async_change(change)
                    self.coordinator.accept_head_reset = self.coordinator.head_error == "head_counter_reset"
                    await self.coordinator.async_request_refresh()
                except OSError:
                    errors["base"] = "save_failed"
                else:
                    return self._finish()
        return self.async_show_form(step_id="resume", data_schema=vol.Schema({
            vol.Required("confirm", default=False): bool}), errors=errors)

    async def async_step_import_backup(self, user_input=None):
        errors = {}
        if user_input:
            if user_input.get("confirm") is not True:
                errors["base"] = "confirm_required"
            else:
                try:
                    state = json.loads(user_input["backup_json"])
                    # HA diagnostic downloads may wrap the maintenance backup.
                    if isinstance(state, dict) and "data" in state and isinstance(state["data"], dict):
                        state = state["data"]
                    if isinstance(state, dict) and "maintenance_backup" in state:
                        state = state["maintenance_backup"]
                    await self.coordinator.async_import(state)
                except (ValueError, KeyError, TypeError):
                    errors["base"] = "invalid_backup"
                except OSError:
                    errors["base"] = "save_failed"
                else:
                    return self._finish()
        return self.async_show_form(step_id="import_backup", data_schema=vol.Schema({
            vol.Required("backup_json"): selector.TextSelector(selector.TextSelectorConfig(multiline=True)),
            vol.Required("confirm", default=False): bool}), errors=errors)
