"""Downloadable maintenance backup with network details and secrets omitted."""

from copy import deepcopy


async def async_get_config_entry_diagnostics(hass, entry):
    coordinator = entry.runtime_data
    state = deepcopy(coordinator.state)
    # The integration config (host/key) is intentionally never included.
    state["connection"] = {"url": "", "enabled": True, "status": "unknown", "lastSuccess": None}
    return {"maintenance_backup": state, "catalog_version": coordinator.catalog["version"],
            "printer_error": coordinator.error}
