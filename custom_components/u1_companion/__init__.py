"""U1 Care, configured in Home Assistant without a PC bridge or YAML."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.start import async_at_started

from .const import DOMAIN, PLATFORMS, STORAGE_VERSION
from .coordinator import U1Coordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = U1Coordinator(hass, entry)
    await coordinator.async_load()
    # Offline printing hardware must not hide locally stored maintenance dates.
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    from .auto_dashboard import async_initialize_dashboard
    async def setup_dashboard(started_hass):
        await async_initialize_dashboard(started_hass, entry)
    entry.async_on_unload(async_at_started(hass, setup_dashboard))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}").async_remove()
    await Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}.before_import").async_remove()
