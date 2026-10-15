"""Printer connectivity is separate from maintenance availability."""

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity

from .entity import U1Entity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([U1Connection(entry.runtime_data)])


class U1Connection(U1Entity, BinarySensorEntity):
    _attr_name = "Connexion U1"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator):
        super().__init__(coordinator, "connection")

    @property
    def is_on(self):
        return self.coordinator.data["connected"]

    @property
    def extra_state_attributes(self):
        return {"status": self.coordinator.data["connection_error"],
                "last_success": self.coordinator.data["last_success"]}
