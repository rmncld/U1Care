"""Maintenance states and retained printing hours."""

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import UnitOfTime

from .entity import U1Entity

ICONS = {"inspection": "mdi:clipboard-check-outline", "motion": "mdi:axis-arrow",
         "toolheads": "mdi:printer-3d-nozzle-outline"}


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = entry.runtime_data
    async_add_entities([U1Hours(coordinator), U1Overall(coordinator),
                        *(U1Maintenance(coordinator, t) for t in coordinator.catalog["tasks"])])


def _display(status):
    if status.get("remaining") is None:
        return status["label"]
    return f"{status['label']} · {status['remaining']:g} {status['unit']}".strip()


class U1Hours(U1Entity, SensorEntity):
    _attr_name = "Heures de l’historique"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTime.HOURS
    _attr_suggested_display_precision = 1
    _attr_icon = "mdi:timer-outline"

    def __init__(self, coordinator):
        super().__init__(coordinator, "history_hours")

    @property
    def native_value(self):
        return self.coordinator.data["hours"]

    @property
    def available(self):
        return super().available and self.native_value is not None

    @property
    def extra_state_attributes(self):
        return {"source": self.coordinator.data["hours_source"],
                "last_success": self.coordinator.data["last_success"],
                "scope": "Historique conservé ; hors impression en cours ; total à vie non garanti"}


class U1Overall(U1Entity, SensorEntity):
    _attr_name = "Maintenance générale"
    _attr_icon = "mdi:clipboard-pulse-outline"

    def __init__(self, coordinator):
        super().__init__(coordinator, "maintenance_overall")

    @property
    def native_value(self):
        return _display(self.coordinator.data["overall"])

    @property
    def extra_state_attributes(self):
        return {"level": self.coordinator.data["overall"]["level"],
                "catalog_version": self.coordinator.catalog["version"],
                "printer_error": self.coordinator.data["connection_error"],
                "usage": "Configurer l’intégration pour consigner un entretien et lire sa procédure"}


class U1Maintenance(U1Entity, SensorEntity):
    def __init__(self, coordinator, task):
        super().__init__(coordinator, task["id"])
        self.task_id = task["id"]
        self._attr_name = task["title"]
        self._attr_icon = ICONS[task["group"]]

    @property
    def native_value(self):
        return _display(self.coordinator.data["tasks"][self.task_id])

    @property
    def extra_state_attributes(self):
        status = self.coordinator.data["tasks"][self.task_id]
        # Recent events are available without publishing private maintenance notes.
        events = [h for h in self.coordinator.state["history"] if h["taskId"] == self.task_id]
        return {**{k: v for k, v in status.items() if k not in ("title", "steps")},
                "procedure": status["steps"], "catalog_version": self.coordinator.catalog["version"],
                "event_count": len(events), "recent_event_dates": [h["date"] for h in events[-5:]]}
