from __future__ import annotations

import logging
from datetime import timedelta
from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import HVACMode, ClimateEntityFeature
from homeassistant.const import UnitOfTemperature, STATE_ON, STATE_OFF, STATE_UNAVAILABLE, STATE_UNKNOWN, ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    DOMAIN, CONF_ZONES, ZK_ID, ZK_NAME, ZK_SENSOR_AIR, ZK_SENSOR_FLOOR, ZK_SENSOR_RH,
    ZK_SWITCH_ACTUATOR, ZK_SUPPORT_MODE, ZK_FLOOR_LIMITS, ZK_OPEN_S, ZK_CLOSE_S,
    ZK_ZONE_MIN_ON, ZK_ZONE_MIN_OFF, ZK_WINDOW_SWITCH, EVT_ZONE_STATUS
)
from .helpers import dew_point_c, get_state_float, get_state_str, co_mode_from_entity
from .config_flow import get_current_config

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=5)  # VT publishes status every 5s

async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    # Use unified config loading that merges options over data
    current_config = get_current_config(entry)
    zones = current_config.get(CONF_ZONES, [])
    entities = [VirtualThermostat(hass, entry, zconf) for zconf in zones]
    async_add_entities(entities, update_before_add=True)

class VirtualThermostat(ClimateEntity, RestoreEntity):
    """Virtual thermostat representing one UFH cooling/heating zone.
    This entity is *not* directly switching the actuator. It reports status
    (including needs) to the ZoneManager which sequences the on/off slots.
    """

    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(self, hass: HomeAssistant, entry, zconf: dict):
        self.hass = hass
        self.entry = entry
        self.zid = zconf.get(ZK_ID)
        self._name = zconf.get(ZK_NAME, self.zid)
        self._z = zconf

        # Per-mode setpoints
        self._t_heat = 22.0
        self._t_cool = 24.0
        self._target_temp = self._t_cool  # will be switched by global mode

        # Live readings
        self._t_air = None
        self._t_floor = None
        self._rh = None
        self._dew = None
        self._window_open = False

        # UI mode (we don't expose HVACMode.COOL/HEAT switch here; the global co_mode controls behavior)
        self._hvac_mode = HVACMode.AUTO  # cosmetic; real mode is global

        # Simple publish timer
        self._unsub_pub = None

    @property
    def name(self):
        return f"VT {self._name}"

    @property
    def unique_id(self):
        return f"{DOMAIN}.{self.zid}"

    @property
    def hvac_modes(self):
        # Keep simple UI; actual mode is global. You may expose OFF as well.
        return [HVACMode.AUTO]

    @property
    def hvac_mode(self):
        return self._hvac_mode

    @property
    def current_temperature(self):
        return self._t_air

    @property
    def target_temperature(self):
        return self._target_temp

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self._unsub_pub = async_track_time_interval(self.hass, self._async_publish_status, SCAN_INTERVAL)

        # restore last target temps if any
        last = await self.async_get_last_state()
        if last and (ATTR_TEMPERATURE in last.attributes):
            # last target doesn't tell us heat/cool split; keep defaults for MVP
            pass

    async def async_will_remove_from_hass(self):
        if self._unsub_pub:
            self._unsub_pub()
            self._unsub_pub = None

    async def async_set_temperature(self, **kwargs):
        """Set per-mode setpoint. Only the *current global mode* is updated."""
        t = kwargs.get(ATTR_TEMPERATURE)
        if t is None:
            return
        co_mode = co_mode_from_entity(self.hass, self.entry.data)
        if co_mode == "COOL":
            self._t_cool = float(t)
        else:
            self._t_heat = float(t)
        self._recompute_target()
        self.async_write_ha_state()

    def _recompute_target(self):
        co_mode = co_mode_from_entity(self.hass, self.entry.data)
        self._target_temp = self._t_cool if co_mode == "COOL" else self._t_heat

    async def async_update(self):
        """Pull sensor states and recompute dew point + attributes."""
        z = self._z
        self._t_air = get_state_float(self.hass, z.get(ZK_SENSOR_AIR))
        self._t_floor = get_state_float(self.hass, z.get(ZK_SENSOR_FLOOR))
        self._rh = get_state_float(self.hass, z.get(ZK_SENSOR_RH))
        self._window_open = (get_state_str(self.hass, z.get(ZK_WINDOW_SWITCH)) == "on")

        if self._t_air is not None and self._rh is not None:
            self._dew = dew_point_c(self._t_air, self._rh)
        else:
            self._dew = None

        self._recompute_target()

    @property
    def extra_state_attributes(self):
        z = self._z
        return {
            "zone_id": self.zid,
            "support_mode": z.get(ZK_SUPPORT_MODE),
            "window_open": self._window_open,
            "t_air": self._t_air,
            "t_floor": self._t_floor,
            "rh": self._rh,
            "dew_point": self._dew,
            "t_set_heat": self._t_heat,
            "t_set_cool": self._t_cool,
            "actuator_open_s": z.get(ZK_OPEN_S),
            "actuator_close_s": z.get(ZK_CLOSE_S),
            "floor_limits": z.get(ZK_FLOOR_LIMITS)
        }

    async def _async_publish_status(self, now):
        """Publish a compact status payload to the ZoneManager via hass.bus."""
        co_mode = co_mode_from_entity(self.hass, self.entry.data)

        # Compute sign-consistent delta for COOL/HEAT
        delta = None
        if self._t_air is not None:
            target = self._t_cool if co_mode == "COOL" else self._t_heat
            delta = (target - self._t_air)  # positive = too cold in HEAT, negative = too hot in COOL

        payload = {
            "zone_id": self.zid,
            "name": self._name,
            "co_mode": co_mode,                    # "HEAT" | "COOL"
            "support_mode": self._z.get(ZK_SUPPORT_MODE, "BOTH"),
            "eligible_window": (not self._window_open),
            "t_air": self._t_air,
            "t_floor": self._t_floor,
            "rh": self._rh,
            "dew_point": self._dew,
            "delta_air": delta,
            "actuator": {
                "entity_id": self._z.get(ZK_SWITCH_ACTUATOR),
                "open_s": self._z.get(ZK_OPEN_S, 20),
                "close_s": self._z.get(ZK_CLOSE_S, 20),
            },
            "limits": {
                "floor": self._z.get(ZK_FLOOR_LIMITS, {}),
                "zone_min_on_s": self._z.get(ZK_ZONE_MIN_ON, 180),
                "zone_min_off_s": self._z.get(ZK_ZONE_MIN_OFF, 180),
            },
            "window_open": self._window_open,
        }
        self.hass.bus.async_fire(EVT_ZONE_STATUS, payload)
