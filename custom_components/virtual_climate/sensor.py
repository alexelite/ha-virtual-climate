from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo

from .const import DATA_KEY_MANAGER, DOMAIN


@dataclass(frozen=True, kw_only=True)
class VirtualClimateSensorDescription(SensorEntityDescription):
    value_key: str


SENSOR_DESCRIPTIONS: tuple[VirtualClimateSensorDescription, ...] = (
    VirtualClimateSensorDescription(
        key="system_mode",
        translation_key="system_mode",
        name="System mode",
        icon="mdi:thermostat-box",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=["OFF", "HEAT", "COOL"],
        value_key="system_mode",
    ),
    VirtualClimateSensorDescription(
        key="coordinator_phase",
        translation_key="coordinator_phase",
        name="Coordinator phase",
        icon="mdi:source-branch",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_key="coordinator_phase",
    ),
    VirtualClimateSensorDescription(
        key="packing_mode",
        translation_key="packing_mode",
        name="Packing mode",
        icon="mdi:view-sequential",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=["simultaneous", "staggered"],
        value_key="packing_mode",
    ),
    VirtualClimateSensorDescription(
        key="aggregated_demand_ratio",
        translation_key="aggregated_demand_ratio",
        name="Aggregated demand ratio",
        icon="mdi:chart-line",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_key="aggregated_demand_ratio",
    ),
    VirtualClimateSensorDescription(
        key="plant_state",
        translation_key="plant_state",
        name="Plant state",
        icon="mdi:state-machine",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=["off", "starting", "running", "stopping"],
        value_key="plant_state",
    ),
    VirtualClimateSensorDescription(
        key="plant_mode",
        translation_key="plant_mode",
        name="Plant mode",
        icon="mdi:hvac",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=["OFF", "HEAT", "COOL"],
        value_key="plant_mode",
    ),
    VirtualClimateSensorDescription(
        key="scheduled_zones",
        translation_key="scheduled_zones",
        name="Scheduled zones",
        icon="mdi:format-list-numbered",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_key="scheduled_zones",
    ),
    VirtualClimateSensorDescription(
        key="running_zones",
        translation_key="running_zones",
        name="Running zones",
        icon="mdi:play-circle-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_key="running_zones",
    ),
    VirtualClimateSensorDescription(
        key="blocked_zones",
        translation_key="blocked_zones",
        name="Blocked zones",
        icon="mdi:alert-circle-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_key="blocked_zones",
    ),
    VirtualClimateSensorDescription(
        key="total_zones",
        translation_key="total_zones",
        name="Total zones",
        icon="mdi:counter",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_key="total_zones",
    ),
    VirtualClimateSensorDescription(
        key="cycle_length_s",
        translation_key="cycle_length_s",
        name="Cycle length",
        icon="mdi:timer-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        value_key="cycle_length_s",
    ),
)


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    manager = hass.data[DOMAIN][entry.entry_id][DATA_KEY_MANAGER]
    async_add_entities(
        VirtualClimateGlobalSensor(entry, manager, description)
        for description in SENSOR_DESCRIPTIONS
    )


class VirtualClimateGlobalSensor(SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, entry, manager, description: VirtualClimateSensorDescription) -> None:
        self.entry = entry
        self.manager = manager
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_diagnostics")},
            name="Virtual Climate Diagnostics",
        )
        self._attr_native_value = self._read_value()
        self._unsub_listener = None

    async def async_added_to_hass(self) -> None:
        self._attr_native_value = self._read_value()

        @callback
        def _handle_update() -> None:
            self._attr_native_value = self._read_value()
            self.async_write_ha_state()

        self._unsub_listener = self.manager.async_add_listener(_handle_update)

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub_listener:
            self._unsub_listener()
            self._unsub_listener = None

    def _read_value(self) -> Any:
        diagnostics = self.manager.get_global_diagnostics()
        return diagnostics.get(self.entity_description.value_key)
