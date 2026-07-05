from __future__ import annotations

import logging
from datetime import timedelta
from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import HVACAction, HVACMode, ClimateEntityFeature
from homeassistant.const import UnitOfTemperature, STATE_ON, STATE_OFF, STATE_UNAVAILABLE, STATE_UNKNOWN, ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    DOMAIN, CONF_ZONES, ZK_ID, ZK_NAME, ZK_SENSOR_AIR, ZK_SENSOR_FLOOR, ZK_SENSOR_RH,
    ZK_SWITCH_ACTUATOR, ZK_SUPPORT_MODE, ZK_FLOOR_LIMITS, ZK_OPEN_S, ZK_CLOSE_S,
    ZK_ZONE_MIN_ON, ZK_ZONE_MIN_OFF, ZK_WINDOW_SWITCH, EVT_ZONE_STATUS, EVT_ZONE_SCHEDULE,
    EVENT_ENTRY_ID,
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
        self._last_active_co_mode = "HEAT"
        self._manual_off = False

        # UI mode: AUTO follows the global system mode, OFF is a manual override.
        self._hvac_mode = HVACMode.AUTO

        # Simple publish timer
        self._unsub_pub = None
        self._unsub_schedule = None
        self._coordinator_diag = {}

    def _zone_config(self) -> dict:
        """Return the latest merged zone config for this entity."""
        zones = get_current_config(self.entry).get(CONF_ZONES, [])
        for zone in zones:
            if zone.get(ZK_ID) == self.zid:
                self._z = zone
                self._name = zone.get(ZK_NAME, self._name)
                return zone
        return self._z

    @property
    def name(self):
        return f"VT {self._name}"

    @property
    def unique_id(self):
        return f"{DOMAIN}.{self.zid}"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self.entry.entry_id}_{self.zid}")},
            name=f"VT {self._name}",
            model="Virtual Climate Zone",
            manufacturer="Virtual Climate",
        )

    @property
    def hvac_modes(self):
        return [HVACMode.AUTO, HVACMode.OFF]

    @property
    def hvac_mode(self):
        return HVACMode.OFF if self._manual_off else HVACMode.AUTO

    def _mode_supported(self, co_mode: str) -> bool:
        support_mode = (self._zone_config().get(ZK_SUPPORT_MODE) or "BOTH").upper()
        if co_mode == "HEAT":
            return support_mode in ("HEAT", "BOTH")
        if co_mode == "COOL":
            return support_mode in ("COOL", "BOTH")
        return True

    def _display_co_mode(self) -> str:
        """Return the mode that should drive UI setpoint display and edits."""
        co_mode = co_mode_from_entity(self.hass, get_current_config(self.entry))
        if co_mode == "OFF":
            co_mode = self._last_active_co_mode

        if self._mode_supported(co_mode):
            return co_mode

        support_mode = (self._zone_config().get(ZK_SUPPORT_MODE) or "BOTH").upper()
        if support_mode == "HEAT":
            return "HEAT"
        if support_mode == "COOL":
            return "COOL"
        return co_mode

    @property
    def hvac_action(self):
        co_mode = co_mode_from_entity(self.hass, get_current_config(self.entry))
        if self._manual_off or co_mode == "OFF":
            return HVACAction.OFF

        if not self._mode_supported(co_mode):
            return HVACAction.IDLE

        if self._t_air is None:
            return HVACAction.IDLE

        target = self._t_cool if co_mode == "COOL" else self._t_heat
        delta = target - self._t_air
        if co_mode == "HEAT" and delta > 0:
            return HVACAction.HEATING
        if co_mode == "COOL" and delta < 0:
            return HVACAction.COOLING
        return HVACAction.IDLE

    @property
    def current_temperature(self):
        return self._t_air

    @property
    def current_humidity(self):
        return self._rh

    @property
    def target_temperature(self):
        return self._target_temp

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self._unsub_pub = async_track_time_interval(self.hass, self._async_publish_status, SCAN_INTERVAL)
        self._unsub_schedule = self.hass.bus.async_listen(EVT_ZONE_SCHEDULE, self._on_zone_schedule)

        last = await self.async_get_last_state()
        if not last:
            return

        if last.state == HVACMode.OFF:
            self._manual_off = True
        if "t_set_heat" in last.attributes:
            self._t_heat = float(last.attributes["t_set_heat"])
        if "t_set_cool" in last.attributes:
            self._t_cool = float(last.attributes["t_set_cool"])
        if last.attributes.get("last_active_co_mode") in ("HEAT", "COOL"):
            self._last_active_co_mode = last.attributes["last_active_co_mode"]
        self._recompute_target()

    async def async_will_remove_from_hass(self):
        if self._unsub_pub:
            self._unsub_pub()
            self._unsub_pub = None
        if self._unsub_schedule:
            self._unsub_schedule()
            self._unsub_schedule = None

    @callback
    def _on_zone_schedule(self, event):
        data = event.data or {}
        if data.get(EVENT_ENTRY_ID) != self.entry.entry_id:
            return
        if data.get("zone_id") != self.zid:
            return
        self._coordinator_diag = dict(data)
        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode):
        """Set zone AUTO/OFF. OFF acts as a manual override."""
        self._manual_off = hvac_mode == HVACMode.OFF
        self._hvac_mode = HVACMode.OFF if self._manual_off else HVACMode.AUTO

        if self._manual_off:
            ent = self._zone_config().get(ZK_SWITCH_ACTUATOR)
            if ent:
                await self.hass.services.async_call(
                    "homeassistant",
                    "turn_off",
                    {"entity_id": ent},
                    blocking=False,
                )

        self.async_write_ha_state()
        await self._async_publish_status(None)

    async def async_set_temperature(self, **kwargs):
        """Set the setpoint for the mode currently exposed in the UI."""
        t = kwargs.get(ATTR_TEMPERATURE)
        if t is None:
            return
        co_mode = self._display_co_mode()
        if co_mode == "COOL":
            self._t_cool = float(t)
        else:
            self._t_heat = float(t)
        self._recompute_target()
        self.async_write_ha_state()

    def _recompute_target(self):
        co_mode = co_mode_from_entity(self.hass, get_current_config(self.entry))
        if co_mode in ("HEAT", "COOL"):
            self._last_active_co_mode = co_mode
        active_mode = self._display_co_mode()
        self._target_temp = self._t_cool if active_mode == "COOL" else self._t_heat

    def _floor_limit_state(self) -> str:
        floor_limits = self._zone_config().get(ZK_FLOOR_LIMITS) or {}
        if self._t_floor is None:
            return "no_floor_sensor"
        if not floor_limits:
            return "no_floor_limits"

        active_mode = self._display_co_mode()
        if active_mode == "HEAT":
            heat_max = floor_limits.get("heat_max")
            heat_min = floor_limits.get("heat_min")
            if heat_max is not None and self._t_floor >= float(heat_max):
                return "heat_max_reached"
            if heat_min is not None and self._t_floor <= float(heat_min):
                return "below_heat_min"
        elif active_mode == "COOL":
            cool_min = floor_limits.get("cool_min")
            cool_max = floor_limits.get("cool_max")
            if cool_min is not None and self._t_floor <= float(cool_min):
                return "cool_min_reached"
            if cool_max is not None and self._t_floor >= float(cool_max):
                return "above_cool_max"
        return "ok"

    async def async_update(self):
        """Pull sensor states and recompute dew point + attributes."""
        z = self._zone_config()
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
        z = self._zone_config()
        coordinator = self._coordinator_diag
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
            "system_mode": co_mode_from_entity(self.hass, get_current_config(self.entry)),
            "zone_mode": "OFF" if self._manual_off else "AUTO",
            "last_active_co_mode": self._last_active_co_mode,
            "floor_limit_state": self._floor_limit_state(),
            "actuator_open_s": z.get(ZK_OPEN_S),
            "actuator_close_s": z.get(ZK_CLOSE_S),
            "floor_limits": z.get(ZK_FLOOR_LIMITS),
            "coordinator_status": coordinator.get("coordinator_status"),
            "coordinator_phase": coordinator.get("coordinator_phase"),
            "coordinator_cycle_active": coordinator.get("cycle_active"),
            "coordinator_cycle_length_s": coordinator.get("cycle_length_s"),
            "coordinator_packing_mode": coordinator.get("packing_mode"),
            "coordinator_scheduled": coordinator.get("scheduled"),
            "coordinator_running": coordinator.get("running"),
            "coordinator_requested_fraction": coordinator.get("requested_fraction"),
            "coordinator_requested_t_on_s": coordinator.get("requested_t_on_s"),
            "coordinator_scheduled_t_on_s": coordinator.get("scheduled_t_on_s"),
            "coordinator_start_offset_s": coordinator.get("start_offset_s"),
            "coordinator_arbitration_rank": coordinator.get("arbitration_rank"),
            "coordinator_blocked_by": coordinator.get("blocked_by"),
            "coordinator_block_reasons": coordinator.get("last_block_reasons", []),
            "coordinator_aggregated_demand_ratio": coordinator.get("aggregated_demand_ratio"),
            "plant_state": coordinator.get("plant_state"),
            "plant_mode": coordinator.get("plant_mode"),
        }

    async def _async_publish_status(self, now):
        """Publish a compact status payload to the ZoneManager via hass.bus."""
        co_mode = co_mode_from_entity(self.hass, get_current_config(self.entry))

        # Compute sign-consistent delta for COOL/HEAT
        delta = None
        active_mode = self._last_active_co_mode if co_mode == "OFF" else co_mode
        if self._t_air is not None:
            target = self._t_cool if active_mode == "COOL" else self._t_heat
            delta = (target - self._t_air)  # positive = too cold in HEAT, negative = too hot in COOL

        payload = {
            EVENT_ENTRY_ID: self.entry.entry_id,
            "zone_id": self.zid,
            "name": self._name,
            "co_mode": co_mode,                    # "HEAT" | "COOL" | "OFF"
            "active_co_mode": active_mode,
            "manual_off": self._manual_off,
            "zone_hvac_mode": "OFF" if self._manual_off else "AUTO",
            "support_mode": self._zone_config().get(ZK_SUPPORT_MODE, "BOTH"),
            "eligible_window": (not self._window_open),
            "t_air": self._t_air,
            "t_floor": self._t_floor,
            "rh": self._rh,
            "dew_point": self._dew,
            "delta_air": delta,
            "actuator": {
                "entity_id": self._zone_config().get(ZK_SWITCH_ACTUATOR),
                "open_s": self._zone_config().get(ZK_OPEN_S, 20),
                "close_s": self._zone_config().get(ZK_CLOSE_S, 20),
            },
            "limits": {
                "floor": self._zone_config().get(ZK_FLOOR_LIMITS, {}),
                "zone_min_on_s": self._zone_config().get(ZK_ZONE_MIN_ON, 180),
                "zone_min_off_s": self._zone_config().get(ZK_ZONE_MIN_OFF, 180),
            },
            "window_open": self._window_open,
            "floor_limit_state": self._floor_limit_state(),
        }
        self.hass.bus.async_fire(EVT_ZONE_STATUS, payload)
