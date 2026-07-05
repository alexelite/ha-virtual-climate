from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo

from .const import DATA_KEY_MANAGER, DOMAIN


BINARY_SENSOR_DESCRIPTIONS: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="cycle_active",
        translation_key="cycle_active",
        name="Cycle active",
        icon="mdi:timer-play-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    manager = hass.data[DOMAIN][entry.entry_id][DATA_KEY_MANAGER]
    async_add_entities(
        VirtualClimateGlobalBinarySensor(entry, manager, description)
        for description in BINARY_SENSOR_DESCRIPTIONS
    )


class VirtualClimateGlobalBinarySensor(BinarySensorEntity):
    _attr_has_entity_name = True

    def __init__(self, entry, manager, description: BinarySensorEntityDescription) -> None:
        self.entry = entry
        self.manager = manager
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_diagnostics")},
            name="Virtual Climate Diagnostics",
        )
        self._attr_is_on = self._read_value()
        self._unsub_listener = None

    async def async_added_to_hass(self) -> None:
        self._attr_is_on = self._read_value()

        @callback
        def _handle_update() -> None:
            self._attr_is_on = self._read_value()
            self.async_write_ha_state()

        self._unsub_listener = self.manager.async_add_listener(_handle_update)

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub_listener:
            self._unsub_listener()
            self._unsub_listener = None

    def _read_value(self) -> bool:
        diagnostics = self.manager.get_global_diagnostics()
        return bool(diagnostics.get(self.entity_description.key))
