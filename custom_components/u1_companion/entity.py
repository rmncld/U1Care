"""Common device information; entry ID stays stable when its IP changes."""

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, VERSION


class U1Entity(CoordinatorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, key):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry.entry_id)},
            name=coordinator.entry.title,
            manufacturer="Snapmaker",
            model="U1 — DÉMONSTRATION" if coordinator.demo else "U1 — suivi indépendant Care",
            sw_version=f"U1 Care {VERSION}",
            configuration_url=coordinator.api.url if coordinator.api else None,
        )
