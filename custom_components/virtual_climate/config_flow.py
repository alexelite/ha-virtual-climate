from __future__ import annotations

import json
from typing import Any, Dict, List

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.selector import selector
from homeassistant.core import callback

DOMAIN = "virtual_climate"

# Global keys stored on the config entry
CONF_GLOBAL_CO_MODE_ENTITY = "global_co_mode_entity"
CONF_PACKING_MODE = "packing_mode"
CONF_T_CYCLE_SECONDS = "t_cycle_seconds"
CONF_T_CYCLE_MIN = "t_cycle_min"
CONF_T_CYCLE_MAX = "t_cycle_max"
CONF_RH_ALERT = "rh_alert"
CONF_RH_FAULT = "rh_fault"
CONF_DP_SAFETY_MARGIN = "dp_safety_margin_c"
CONF_HEATING_SOURCE_ENTITY = "heating_source_entity"
CONF_COOLING_SOURCE_ENTITY = "cooling_source_entity"
CONF_CHANGEOVER_ENTITY = "changeover_entity"
CONF_CIRCULATION_PUMP_ENTITY = "circulation_pump_entity"
CONF_TARGET_SUPPLY_TEMPERATURE_ENTITY = "target_supply_temperature_entity"
CONF_HEATING_SUPPLY_TARGET = "heating_supply_target"
CONF_COOLING_SUPPLY_TARGET = "cooling_supply_target"
CONF_PUMP_START_DELAY_SECONDS = "pump_start_delay_seconds"
CONF_HEATING_SOURCE_START_DELAY_SECONDS = "heating_source_start_delay_seconds"
CONF_COOLING_SOURCE_START_DELAY_SECONDS = "cooling_source_start_delay_seconds"
CONF_MINIMUM_RUN_TIME_SECONDS = "minimum_run_time_seconds"
CONF_PUMP_POST_RUN_SECONDS = "pump_post_run_seconds"
CONF_MINIMUM_OFF_TIME_SECONDS = "minimum_off_time_seconds"
CONF_ZONES = "zones"

# Zone dict keys
ZK_ID = "id"
ZK_NAME = "name"
ZK_SENSOR_AIR = "sensor_air"
ZK_SENSOR_FLOOR = "sensor_floor"
ZK_SENSOR_RH = "sensor_rh"
ZK_SWITCH_ACT = "switch_actuator"
ZK_SUPPORT_MODE = "support_mode"  # "HEAT" | "COOL" | "BOTH"
ZK_FLOOR_LIMITS = "floor_limits"  # {"heat_min":float,"heat_max":float,"cool_min":float,"cool_max":float}
ZK_OPEN_S = "open_s"
ZK_CLOSE_S = "close_s"
ZK_ZONE_MIN_ON = "zone_min_on_s"
ZK_ZONE_MIN_OFF = "zone_min_off_s"
ZK_WINDOW_SWITCH = "window_switch"

DEFAULTS = {
    CONF_PACKING_MODE: "simultaneous",
    CONF_T_CYCLE_SECONDS: 12 * 60,
    CONF_T_CYCLE_MIN: 6 * 60,
    CONF_T_CYCLE_MAX: 24 * 60,
    CONF_RH_ALERT: 60.0,
    CONF_RH_FAULT: 70.0,
    CONF_DP_SAFETY_MARGIN: 2.0,
    CONF_HEATING_SOURCE_ENTITY: None,
    CONF_COOLING_SOURCE_ENTITY: None,
    CONF_CHANGEOVER_ENTITY: None,
    CONF_CIRCULATION_PUMP_ENTITY: None,
    CONF_TARGET_SUPPLY_TEMPERATURE_ENTITY: None,
    CONF_HEATING_SUPPLY_TARGET: 32.0,
    CONF_COOLING_SUPPLY_TARGET: 18.0,
    CONF_PUMP_START_DELAY_SECONDS: 0,
    CONF_HEATING_SOURCE_START_DELAY_SECONDS: 30,
    CONF_COOLING_SOURCE_START_DELAY_SECONDS: 30,
    CONF_MINIMUM_RUN_TIME_SECONDS: 300,
    CONF_PUMP_POST_RUN_SECONDS: 120,
    CONF_MINIMUM_OFF_TIME_SECONDS: 180,
    ZK_OPEN_S: 60,
    ZK_CLOSE_S: 60,
    ZK_ZONE_MIN_ON: 180,
    ZK_ZONE_MIN_OFF: 180,
}

GLOBAL_CONFIG_KEYS = (
    CONF_GLOBAL_CO_MODE_ENTITY,
    CONF_PACKING_MODE,
    CONF_T_CYCLE_SECONDS,
    CONF_T_CYCLE_MIN,
    CONF_T_CYCLE_MAX,
    CONF_RH_ALERT,
    CONF_RH_FAULT,
    CONF_DP_SAFETY_MARGIN,
    CONF_HEATING_SOURCE_ENTITY,
    CONF_COOLING_SOURCE_ENTITY,
    CONF_CHANGEOVER_ENTITY,
    CONF_CIRCULATION_PUMP_ENTITY,
    CONF_TARGET_SUPPLY_TEMPERATURE_ENTITY,
    CONF_HEATING_SUPPLY_TARGET,
    CONF_COOLING_SUPPLY_TARGET,
    CONF_PUMP_START_DELAY_SECONDS,
    CONF_HEATING_SOURCE_START_DELAY_SECONDS,
    CONF_COOLING_SOURCE_START_DELAY_SECONDS,
    CONF_MINIMUM_RUN_TIME_SECONDS,
    CONF_PUMP_POST_RUN_SECONDS,
    CONF_MINIMUM_OFF_TIME_SECONDS,
)


def _optional_entity_field(key: str, domains: list[str], default: Any = ...):
    """Build an optional entity selector field that can remain unset."""
    schema_key = vol.Optional(key) if default in (..., None, "") else vol.Optional(key, default=default)
    return schema_key, selector({"entity": {"domain": domains}})


def _validate_zone_id_unique(zones: List[Dict[str, Any]], new_id: str) -> None:
    if any(z.get(ZK_ID) == new_id for z in zones):
        raise vol.Invalid(f"Zone id '{new_id}' already exists")


def _coerce_zone_defaults(z: Dict[str, Any]) -> Dict[str, Any]:
    """Fill defaults for optional zone fields and coerce numeric subfields."""
    z.setdefault(ZK_SUPPORT_MODE, "BOTH")
    z.setdefault(ZK_OPEN_S, DEFAULTS[ZK_OPEN_S])
    z.setdefault(ZK_CLOSE_S, DEFAULTS[ZK_CLOSE_S])
    z.setdefault(ZK_ZONE_MIN_ON, DEFAULTS[ZK_ZONE_MIN_ON])
    z.setdefault(ZK_ZONE_MIN_OFF, DEFAULTS[ZK_ZONE_MIN_OFF])
    z.setdefault(ZK_SENSOR_FLOOR, None)
    z.setdefault(ZK_WINDOW_SWITCH, None)
    if ZK_FLOOR_LIMITS in z and z[ZK_FLOOR_LIMITS] is not None:
        fl = z[ZK_FLOOR_LIMITS]
        for k in ("heat_min", "heat_max", "cool_min", "cool_max"):
            if k in fl and fl[k] is not None:
                fl[k] = float(fl[k])
    else:
        z[ZK_FLOOR_LIMITS] = None
    return z


def _normalize_global_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize and validate global configuration values."""
    normalized = {key: DEFAULTS[key] for key in DEFAULTS if key in GLOBAL_CONFIG_KEYS}
    normalized.update({key: config.get(key) for key in GLOBAL_CONFIG_KEYS if key in config})
    if not normalized.get(CONF_GLOBAL_CO_MODE_ENTITY):
        raise ValueError(f"Missing required field '{CONF_GLOBAL_CO_MODE_ENTITY}'")

    int_fields = (
        CONF_T_CYCLE_SECONDS,
        CONF_T_CYCLE_MIN,
        CONF_T_CYCLE_MAX,
        CONF_PUMP_START_DELAY_SECONDS,
        CONF_HEATING_SOURCE_START_DELAY_SECONDS,
        CONF_COOLING_SOURCE_START_DELAY_SECONDS,
        CONF_MINIMUM_RUN_TIME_SECONDS,
        CONF_PUMP_POST_RUN_SECONDS,
        CONF_MINIMUM_OFF_TIME_SECONDS,
    )
    float_fields = (
        CONF_RH_ALERT,
        CONF_RH_FAULT,
        CONF_DP_SAFETY_MARGIN,
        CONF_HEATING_SUPPLY_TARGET,
        CONF_COOLING_SUPPLY_TARGET,
    )

    for field in int_fields:
        normalized[field] = int(normalized[field])
    for field in float_fields:
        normalized[field] = float(normalized[field])

    return normalized


def _parse_import_payload_value(parsed: Any) -> tuple[Dict[str, Any] | None, List[Dict[str, Any]]]:
    """Parse either a legacy zone array or a full config object."""
    imported_global: Dict[str, Any] | None = None

    if isinstance(parsed, list):
        zones_payload = parsed
    elif isinstance(parsed, dict):
        zones_payload = parsed.get(CONF_ZONES)
        if not isinstance(zones_payload, list) or not zones_payload:
            raise ValueError("JSON object must include a non-empty 'zones' array")

        global_payload = parsed.get("global")
        if global_payload is None:
            global_payload = {key: parsed[key] for key in GLOBAL_CONFIG_KEYS if key in parsed}
        if global_payload:
            if not isinstance(global_payload, dict):
                raise ValueError("'global' must be an object")
            imported_global = _normalize_global_config(global_payload)
    else:
        raise ValueError("JSON must be an object or a non-empty array")

    if not isinstance(zones_payload, list) or not zones_payload:
        raise ValueError("JSON must contain a non-empty zones array")

    zones: List[Dict[str, Any]] = []
    for z in zones_payload:
        if not isinstance(z, dict):
            raise ValueError("Each zone must be an object")
        for req in (ZK_ID, ZK_NAME, ZK_SENSOR_AIR, ZK_SENSOR_RH, ZK_SWITCH_ACT):
            if not z.get(req):
                raise ValueError(f"Missing required field '{req}' in a zone")
        _validate_zone_id_unique(zones, z[ZK_ID])
        zones.append(_coerce_zone_defaults(dict(z)))

    return imported_global, zones


def _parse_import_payload(payload_text: str) -> tuple[Dict[str, Any] | None, List[Dict[str, Any]]]:
    """Parse import payload from JSON text."""
    return _parse_import_payload_value(json.loads(payload_text))


def _build_export_payload(config: Dict[str, Any]) -> Dict[str, Any]:
    """Build a full JSON export payload from the merged config."""
    global_config = {
        key: config.get(key)
        for key in GLOBAL_CONFIG_KEYS
        if config.get(key) is not None
    }
    zones = [dict(zone) for zone in config.get(CONF_ZONES, [])]
    return {
        "global": global_config,
        CONF_ZONES: zones,
    }


def _merge_zone_lists(
    base_zones: List[Dict[str, Any]] | None,
    override_zones: List[Dict[str, Any]] | None,
) -> List[Dict[str, Any]]:
    """Merge zones by id while preserving base order and appending new override zones."""
    base_zones = [dict(zone) for zone in (base_zones or [])]
    override_zones = [dict(zone) for zone in (override_zones or [])]

    overrides_by_id = {
        zone.get(ZK_ID): zone
        for zone in override_zones
        if zone.get(ZK_ID)
    }
    merged_zones: List[Dict[str, Any]] = []
    seen_ids: set[str] = set()

    for zone in base_zones:
        zone_id = zone.get(ZK_ID)
        if not zone_id:
            continue
        merged_zone = dict(zone)
        merged_zone.update(overrides_by_id.get(zone_id, {}))
        merged_zones.append(_coerce_zone_defaults(merged_zone))
        seen_ids.add(zone_id)

    for zone in override_zones:
        zone_id = zone.get(ZK_ID)
        if not zone_id or zone_id in seen_ids:
            continue
        merged_zones.append(_coerce_zone_defaults(dict(zone)))
        seen_ids.add(zone_id)

    return merged_zones


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow with dual path: wizard steps OR JSON import for faster setup."""
    VERSION = 1

    def __init__(self) -> None:
        self._global: Dict[str, Any] = {}
        self._zones: List[Dict[str, Any]] = []

    # ---------- Step 1: Choose setup path ----------
    async def async_step_user(self, user_input=None):
        return self.async_show_menu(
            step_id="user",
            menu_options=["full_json", "manual_global"],
        )

    # ---------- Step 2A: Full JSON import ----------
    async def async_step_full_json(self, user_input=None):
        if user_input is None:
            return self.async_show_form(
                step_id="full_json",
                data_schema=vol.Schema({
                    vol.Required("config_json"): selector({"object": {}})
                })
            )

        errors = {}
        try:
            imported_global, imported_zones = _parse_import_payload_value(user_input.get("config_json"))
            self._global = imported_global or {}
            self._zones = imported_zones
        except Exception:
            errors["base"] = "invalid_config_json"
            return self.async_show_form(
                step_id="full_json",
                data_schema=vol.Schema({
                    vol.Required("config_json"): selector({"object": {}})
                }),
                errors=errors
            )

        data = dict(self._global)
        data[CONF_ZONES] = self._zones
        return self.async_create_entry(title="Virtual Climate", data=data)

    # ---------- Step 2B: Global options ----------
    async def async_step_manual_global(self, user_input=None):
        if user_input is None:
            return self.async_show_form(
                step_id="manual_global",
                data_schema=vol.Schema({
                    vol.Required(CONF_GLOBAL_CO_MODE_ENTITY): selector({
                        "entity": {
                            "multiple": False,
                            "domain": ["input_select", "input_boolean", "select"]
                        }
                    }),
                    vol.Optional(CONF_PACKING_MODE, default=DEFAULTS[CONF_PACKING_MODE]): selector({
                        "select": {"options": ["simultaneous", "staggered"]}
                    }),
                    vol.Optional(CONF_T_CYCLE_SECONDS, default=DEFAULTS[CONF_T_CYCLE_SECONDS]): selector({
                        "number": {"min": 120, "max": 3600, "mode": "box"}
                    }),
                    vol.Optional(CONF_T_CYCLE_MIN, default=DEFAULTS[CONF_T_CYCLE_MIN]): selector({
                        "number": {"min": 60, "max": 3600, "mode": "box"}
                    }),
                    vol.Optional(CONF_T_CYCLE_MAX, default=DEFAULTS[CONF_T_CYCLE_MAX]): selector({
                        "number": {"min": 120, "max": 7200, "mode": "box"}
                    }),
                    vol.Optional(CONF_RH_ALERT, default=DEFAULTS[CONF_RH_ALERT]): selector({
                        "number": {"min": 30, "max": 90, "step": 1, "mode": "box"}
                    }),
                    vol.Optional(CONF_RH_FAULT, default=DEFAULTS[CONF_RH_FAULT]): selector({
                        "number": {"min": 40, "max": 100, "step": 1, "mode": "box"}
                    }),
                    vol.Optional(CONF_DP_SAFETY_MARGIN, default=DEFAULTS[CONF_DP_SAFETY_MARGIN]): selector({
                        "number": {"min": 0.5, "max": 5, "step": 0.5, "mode": "box"}
                    }),
                    _optional_entity_field(CONF_HEATING_SOURCE_ENTITY, ["switch", "input_boolean"])[0]:
                        _optional_entity_field(CONF_HEATING_SOURCE_ENTITY, ["switch", "input_boolean"])[1],
                    _optional_entity_field(CONF_COOLING_SOURCE_ENTITY, ["switch", "input_boolean"])[0]:
                        _optional_entity_field(CONF_COOLING_SOURCE_ENTITY, ["switch", "input_boolean"])[1],
                    _optional_entity_field(CONF_CHANGEOVER_ENTITY, ["switch", "input_boolean"])[0]:
                        _optional_entity_field(CONF_CHANGEOVER_ENTITY, ["switch", "input_boolean"])[1],
                    _optional_entity_field(CONF_CIRCULATION_PUMP_ENTITY, ["switch", "input_boolean"])[0]:
                        _optional_entity_field(CONF_CIRCULATION_PUMP_ENTITY, ["switch", "input_boolean"])[1],
                    _optional_entity_field(CONF_TARGET_SUPPLY_TEMPERATURE_ENTITY, ["number", "input_number"])[0]:
                        _optional_entity_field(CONF_TARGET_SUPPLY_TEMPERATURE_ENTITY, ["number", "input_number"])[1],
                    vol.Optional(CONF_HEATING_SUPPLY_TARGET, default=DEFAULTS[CONF_HEATING_SUPPLY_TARGET]): selector({
                        "number": {"min": 10, "max": 60, "step": 0.5, "mode": "box"}
                    }),
                    vol.Optional(CONF_COOLING_SUPPLY_TARGET, default=DEFAULTS[CONF_COOLING_SUPPLY_TARGET]): selector({
                        "number": {"min": 5, "max": 30, "step": 0.5, "mode": "box"}
                    }),
                    vol.Optional(CONF_PUMP_START_DELAY_SECONDS, default=DEFAULTS[CONF_PUMP_START_DELAY_SECONDS]): selector({
                        "number": {"min": 0, "max": 600, "step": 1, "mode": "box"}
                    }),
                    vol.Optional(CONF_HEATING_SOURCE_START_DELAY_SECONDS, default=DEFAULTS[CONF_HEATING_SOURCE_START_DELAY_SECONDS]): selector({
                        "number": {"min": 0, "max": 900, "step": 1, "mode": "box"}
                    }),
                    vol.Optional(CONF_COOLING_SOURCE_START_DELAY_SECONDS, default=DEFAULTS[CONF_COOLING_SOURCE_START_DELAY_SECONDS]): selector({
                        "number": {"min": 0, "max": 900, "step": 1, "mode": "box"}
                    }),
                    vol.Optional(CONF_MINIMUM_RUN_TIME_SECONDS, default=DEFAULTS[CONF_MINIMUM_RUN_TIME_SECONDS]): selector({
                        "number": {"min": 0, "max": 7200, "step": 1, "mode": "box"}
                    }),
                    vol.Optional(CONF_PUMP_POST_RUN_SECONDS, default=DEFAULTS[CONF_PUMP_POST_RUN_SECONDS]): selector({
                        "number": {"min": 0, "max": 3600, "step": 1, "mode": "box"}
                    }),
                    vol.Optional(CONF_MINIMUM_OFF_TIME_SECONDS, default=DEFAULTS[CONF_MINIMUM_OFF_TIME_SECONDS]): selector({
                        "number": {"min": 0, "max": 7200, "step": 1, "mode": "box"}
                    })
                })
            )
        self._global = dict(user_input)
        return await self.async_step_choose_method()

    # ---------- Step 3: Choose zone method ----------
    async def async_step_choose_method(self, user_input=None):
        """Menu to pick JSON import or zone-by-zone wizard."""
        if user_input is None:
            return self.async_show_menu(
                step_id="choose_method",
                menu_options=["zones_json", "zone_wizard", "finish"]
            )
        # No direct POST expected here; clicking a menu item routes to that step id.

    # ---------- Path A: Zones-only JSON import ----------
    async def async_step_zones_json(self, user_input=None):
        if user_input is None:
            return self.async_show_form(
                step_id="zones_json",
                data_schema=vol.Schema({
                    vol.Required("zones_json"): selector({"text": {"multiline": True}})
                })
            )

        zones_text = (user_input.get("zones_json") or "").strip()
        errors = {}
        try:
            imported_global, imported_zones = _parse_import_payload(zones_text)
            if imported_global:
                self._global.update(imported_global)
            for zone in imported_zones:
                _validate_zone_id_unique(self._zones, zone[ZK_ID])
                self._zones.append(zone)
        except Exception:
            errors["base"] = "invalid_zones_json"
            return self.async_show_form(
                step_id="zones_json",
                data_schema=vol.Schema({
                    vol.Required("zones_json"): selector({"text": {"multiline": True}})
                }),
                errors=errors
            )

        return await self.async_step_choose_method()

    # ---------- Path B: Zone-by-zone wizard ----------
    async def async_step_zone_wizard(self, user_input=None):
        if user_input is None:
            return self.async_show_form(
                step_id="zone_wizard",
                data_schema=vol.Schema({
                    vol.Required(ZK_ID): selector({"text": {}}),
                    vol.Required(ZK_NAME): selector({"text": {}}),
                    vol.Required(ZK_SENSOR_AIR): selector({"entity": {"domain": "sensor"}}),
                    vol.Optional(ZK_SENSOR_FLOOR): selector({"entity": {"domain": "sensor"}}),
                    vol.Required(ZK_SENSOR_RH): selector({"entity": {"domain": "sensor"}}),
                    vol.Required(ZK_SWITCH_ACT): selector({"entity": {"domain": ["switch", "group"]}}),
                    vol.Optional(ZK_WINDOW_SWITCH): selector({"entity": {"domain": "binary_sensor"}}),
                    vol.Optional(ZK_SUPPORT_MODE, default="BOTH"): selector({
                        "select": {"options": ["HEAT", "COOL", "BOTH"]}
                    }),
                    vol.Optional(ZK_FLOOR_LIMITS): selector({"text": {}}),
                    vol.Optional(ZK_OPEN_S, default=DEFAULTS[ZK_OPEN_S]): selector({"number": {"min": 0, "max": 600, "mode": "box"}}),
                    vol.Optional(ZK_CLOSE_S, default=DEFAULTS[ZK_CLOSE_S]): selector({"number": {"min": 0, "max": 600, "mode": "box"}}),
                    vol.Optional(ZK_ZONE_MIN_ON, default=DEFAULTS[ZK_ZONE_MIN_ON]): selector({"number": {"min": 0, "max": 3600, "mode": "box"}}),
                    vol.Optional(ZK_ZONE_MIN_OFF, default=DEFAULTS[ZK_ZONE_MIN_OFF]): selector({"number": {"min": 0, "max": 3600, "mode": "box"}}),
                })
            )

        errors = {}
        try:
            zid = str(user_input[ZK_ID]).strip()
            if not zid:
                raise ValueError("Empty zone id")
            _validate_zone_id_unique(self._zones, zid)

            z: Dict[str, Any] = {
                ZK_ID: zid,
                ZK_NAME: str(user_input[ZK_NAME]).strip(),
                ZK_SENSOR_AIR: user_input[ZK_SENSOR_AIR],
                ZK_SENSOR_FLOOR: user_input.get(ZK_SENSOR_FLOOR) or None,
                ZK_SENSOR_RH: user_input[ZK_SENSOR_RH],
                ZK_SWITCH_ACT: user_input[ZK_SWITCH_ACT],
                ZK_WINDOW_SWITCH: user_input.get(ZK_WINDOW_SWITCH) or None,
                ZK_SUPPORT_MODE: user_input.get(ZK_SUPPORT_MODE, "BOTH"),
                ZK_OPEN_S: int(user_input.get(ZK_OPEN_S, DEFAULTS[ZK_OPEN_S])),
                ZK_CLOSE_S: int(user_input.get(ZK_CLOSE_S, DEFAULTS[ZK_CLOSE_S])),
                ZK_ZONE_MIN_ON: int(user_input.get(ZK_ZONE_MIN_ON, DEFAULTS[ZK_ZONE_MIN_ON])),
                ZK_ZONE_MIN_OFF: int(user_input.get(ZK_ZONE_MIN_OFF, DEFAULTS[ZK_ZONE_MIN_OFF])),
                ZK_FLOOR_LIMITS: None
            }

            fl_txt = user_input.get(ZK_FLOOR_LIMITS)
            if fl_txt:
                fl = json.loads(fl_txt)
                if not isinstance(fl, dict):
                    raise ValueError("floor_limits must be an object")
                z[ZK_FLOOR_LIMITS] = fl

            self._zones.append(_coerce_zone_defaults(z))

        except Exception:
            errors["base"] = "invalid_zone"
            return self.async_show_form(
                step_id="zone_wizard",
                data_schema=vol.Schema({
                    vol.Required(ZK_ID): selector({"text": {}}),
                    vol.Required(ZK_NAME): selector({"text": {}}),
                    vol.Required(ZK_SENSOR_AIR): selector({"entity": {"domain": "sensor"}}),
                    vol.Optional(ZK_SENSOR_FLOOR): selector({"entity": {"domain": "sensor"}}),
                    vol.Required(ZK_SENSOR_RH): selector({"entity": {"domain": "sensor"}}),
                    vol.Required(ZK_SWITCH_ACT): selector({"entity": {"domain": ["switch", "group"]}}),
                    vol.Optional(ZK_WINDOW_SWITCH): selector({"entity": {"domain": "binary_sensor"}}),
                    vol.Optional(ZK_SUPPORT_MODE, default="BOTH"): selector({"select": {"options": ["HEAT", "COOL", "BOTH"]}}),
                    vol.Optional(ZK_FLOOR_LIMITS): selector({"text": {}}),
                    vol.Optional(ZK_OPEN_S, default=DEFAULTS[ZK_OPEN_S]): selector({"number": {"min": 0, "max": 600, "mode": "box"}}),
                    vol.Optional(ZK_CLOSE_S, default=DEFAULTS[ZK_CLOSE_S]): selector({"number": {"min": 0, "max": 600, "mode": "box"}}),
                    vol.Optional(ZK_ZONE_MIN_ON, default=DEFAULTS[ZK_ZONE_MIN_ON]): selector({"number": {"min": 0, "max": 3600, "mode": "box"}}),
                    vol.Optional(ZK_ZONE_MIN_OFF, default=DEFAULTS[ZK_ZONE_MIN_OFF]): selector({"number": {"min": 0, "max": 3600, "mode": "box"}}),
                }),
                errors=errors
            )

        return await self.async_step_choose_method()

    # ---------- Finish ----------
    async def async_step_finish(self, user_input=None):
        if not self._zones:
            return self.async_show_menu(
                step_id="choose_method",
                menu_options=["zones_json", "zone_wizard", "finish"]
            )

        data = dict(self._global)
        data[CONF_ZONES] = self._zones
        return self.async_create_entry(title="Virtual Climate", data=data)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return VirtualClimateOptionsFlow(config_entry)


def get_current_config(entry: config_entries.ConfigEntry) -> Dict[str, Any]:
    """Get current configuration by merging options over data."""
    data = entry.data.copy()
    if entry.options:
        # Merge options over data
        data.update(entry.options)
        # Handle zones specially - merge zone options
        if "zones" in entry.options and "zones" in entry.data:
            data["zones"] = _merge_zone_lists(
                entry.data.get("zones", []),
                entry.options.get("zones", []),
            )
    return data


class VirtualClimateOptionsFlow(config_entries.OptionsFlow):
    """Options flow for Virtual Climate integration."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        """Initialize options flow."""
        self._config_entry = config_entry
        self.current_config = get_current_config(config_entry)

    def _get_zone_edit_defaults(
        self, selected_zone: Dict[str, Any], user_input: Dict[str, Any] | None = None
    ) -> Dict[str, Any]:
        """Build normalized defaults for the zone edit form."""
        floor_limits = selected_zone.get(ZK_FLOOR_LIMITS) or {}
        defaults = {
            ZK_SUPPORT_MODE: selected_zone.get(ZK_SUPPORT_MODE, "BOTH"),
            ZK_SENSOR_AIR: selected_zone.get(ZK_SENSOR_AIR),
            ZK_SENSOR_RH: selected_zone.get(ZK_SENSOR_RH),
            ZK_SWITCH_ACT: selected_zone.get(ZK_SWITCH_ACT),
            ZK_OPEN_S: selected_zone.get(ZK_OPEN_S, DEFAULTS[ZK_OPEN_S]),
            ZK_CLOSE_S: selected_zone.get(ZK_CLOSE_S, DEFAULTS[ZK_CLOSE_S]),
            ZK_ZONE_MIN_ON: selected_zone.get(ZK_ZONE_MIN_ON, DEFAULTS[ZK_ZONE_MIN_ON]),
            ZK_ZONE_MIN_OFF: selected_zone.get(ZK_ZONE_MIN_OFF, DEFAULTS[ZK_ZONE_MIN_OFF]),
            ZK_SENSOR_FLOOR: selected_zone.get(ZK_SENSOR_FLOOR),
            ZK_WINDOW_SWITCH: selected_zone.get(ZK_WINDOW_SWITCH),
            "heat_min": floor_limits.get("heat_min", ""),
            "heat_max": floor_limits.get("heat_max", ""),
            "cool_min": floor_limits.get("cool_min", ""),
            "cool_max": floor_limits.get("cool_max", ""),
        }
        if user_input:
            defaults.update(user_input)
            defaults[ZK_SENSOR_AIR] = user_input.get(ZK_SENSOR_AIR) or selected_zone.get(ZK_SENSOR_AIR)
            defaults[ZK_SENSOR_RH] = user_input.get(ZK_SENSOR_RH) or selected_zone.get(ZK_SENSOR_RH)
            defaults[ZK_SWITCH_ACT] = user_input.get(ZK_SWITCH_ACT) or selected_zone.get(ZK_SWITCH_ACT)
            defaults[ZK_SENSOR_FLOOR] = user_input.get(ZK_SENSOR_FLOOR) or None
            defaults[ZK_WINDOW_SWITCH] = user_input.get(ZK_WINDOW_SWITCH) or None
        return defaults

    def _build_zone_edit_schema(self, defaults: Dict[str, Any]) -> vol.Schema:
        """Build the zone edit schema."""
        sensor_floor_field, sensor_floor_selector = _optional_entity_field(
            ZK_SENSOR_FLOOR,
            ["sensor"],
            defaults[ZK_SENSOR_FLOOR],
        )
        window_switch_field, window_switch_selector = _optional_entity_field(
            ZK_WINDOW_SWITCH,
            ["binary_sensor"],
            defaults[ZK_WINDOW_SWITCH],
        )
        schema: Dict[Any, Any] = {
            vol.Optional(ZK_SUPPORT_MODE, default=defaults[ZK_SUPPORT_MODE]): selector({
                "select": {"options": ["HEAT", "COOL", "BOTH"]}
            }),
            vol.Required(ZK_SENSOR_AIR, default=defaults[ZK_SENSOR_AIR]): selector({
                "entity": {"domain": "sensor"}
            }),
            vol.Required(ZK_SENSOR_RH, default=defaults[ZK_SENSOR_RH]): selector({
                "entity": {"domain": "sensor"}
            }),
            vol.Required(ZK_SWITCH_ACT, default=defaults[ZK_SWITCH_ACT]): selector({
                "entity": {"domain": ["switch", "group"]}
            }),
            sensor_floor_field: sensor_floor_selector,
            vol.Optional("heat_min", default=defaults["heat_min"]): selector({
                "number": {"min": 10, "max": 40, "step": 0.5, "mode": "box"}
            }),
            vol.Optional("heat_max", default=defaults["heat_max"]): selector({
                "number": {"min": 10, "max": 40, "step": 0.5, "mode": "box"}
            }),
            vol.Optional("cool_min", default=defaults["cool_min"]): selector({
                "number": {"min": 10, "max": 40, "step": 0.5, "mode": "box"}
            }),
            vol.Optional("cool_max", default=defaults["cool_max"]): selector({
                "number": {"min": 10, "max": 40, "step": 0.5, "mode": "box"}
            }),
            window_switch_field: window_switch_selector,
            vol.Optional(ZK_OPEN_S, default=defaults[ZK_OPEN_S]): selector({
                "number": {"min": 0, "max": 600, "mode": "box"}
            }),
            vol.Optional(ZK_CLOSE_S, default=defaults[ZK_CLOSE_S]): selector({
                "number": {"min": 0, "max": 600, "mode": "box"}
            }),
            vol.Optional(ZK_ZONE_MIN_ON, default=defaults[ZK_ZONE_MIN_ON]): selector({
                "number": {"min": 0, "max": 3600, "mode": "box"}
            }),
            vol.Optional(ZK_ZONE_MIN_OFF, default=defaults[ZK_ZONE_MIN_OFF]): selector({
                "number": {"min": 0, "max": 3600, "mode": "box"}
            }),
        }
        return vol.Schema(schema)

    async def async_step_init(self, user_input=None):
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_menu(
                step_id="init",
                menu_options=["global_options", "zones_pick", "import_json_replace", "export_json", "finish"]
            )
        return await getattr(self, f"async_step_{user_input}")()

    async def async_step_import_json_replace(self, user_input=None):
        """Replace the entire configuration from imported JSON."""
        if user_input is None:
            return self.async_show_form(
                step_id="import_json_replace",
                data_schema=vol.Schema({
                    vol.Required("config_json"): selector({"object": {}})
                })
            )

        errors = {}
        try:
            imported_global, imported_zones = _parse_import_payload_value(user_input.get("config_json"))
            new_data = dict(imported_global or {})
            new_data[CONF_ZONES] = imported_zones
            self.hass.config_entries.async_update_entry(
                self._config_entry,
                data=new_data,
                options={},
            )
            self.current_config = get_current_config(self._config_entry)
            await self.hass.config_entries.async_reload(self._config_entry.entry_id)
        except Exception:
            errors["base"] = "invalid_config_json"
            return self.async_show_form(
                step_id="import_json_replace",
                data_schema=vol.Schema({
                    vol.Required("config_json"): selector({"object": {}})
                }),
                errors=errors
            )

        return self.async_create_entry(title="", data={})

    async def async_step_export_json(self, user_input=None):
        """Show exportable configuration JSON."""
        export_value = _build_export_payload(self.current_config)
        if user_input is None:
            return self.async_show_form(
                step_id="export_json",
                data_schema=vol.Schema({
                    vol.Required("config_json", default=export_value): selector({"object": {}})
                })
            )

        return await self.async_step_init()

    async def async_step_global_options(self, user_input=None):
        """Handle global options editing."""
        if user_input is None:
            # Pre-fill with current values
            current_global = {
                CONF_GLOBAL_CO_MODE_ENTITY: self.current_config.get(CONF_GLOBAL_CO_MODE_ENTITY, ""),
                CONF_PACKING_MODE: self.current_config.get(CONF_PACKING_MODE, DEFAULTS[CONF_PACKING_MODE]),
                CONF_T_CYCLE_SECONDS: self.current_config.get(CONF_T_CYCLE_SECONDS, DEFAULTS[CONF_T_CYCLE_SECONDS]),
                CONF_T_CYCLE_MIN: self.current_config.get(CONF_T_CYCLE_MIN, DEFAULTS[CONF_T_CYCLE_MIN]),
                CONF_T_CYCLE_MAX: self.current_config.get(CONF_T_CYCLE_MAX, DEFAULTS[CONF_T_CYCLE_MAX]),
                CONF_RH_ALERT: self.current_config.get(CONF_RH_ALERT, DEFAULTS[CONF_RH_ALERT]),
                CONF_RH_FAULT: self.current_config.get(CONF_RH_FAULT, DEFAULTS[CONF_RH_FAULT]),
                CONF_DP_SAFETY_MARGIN: self.current_config.get(CONF_DP_SAFETY_MARGIN, DEFAULTS[CONF_DP_SAFETY_MARGIN]),
                CONF_HEATING_SOURCE_ENTITY: self.current_config.get(CONF_HEATING_SOURCE_ENTITY),
                CONF_COOLING_SOURCE_ENTITY: self.current_config.get(CONF_COOLING_SOURCE_ENTITY),
                CONF_CHANGEOVER_ENTITY: self.current_config.get(CONF_CHANGEOVER_ENTITY),
                CONF_CIRCULATION_PUMP_ENTITY: self.current_config.get(CONF_CIRCULATION_PUMP_ENTITY),
                CONF_TARGET_SUPPLY_TEMPERATURE_ENTITY: self.current_config.get(CONF_TARGET_SUPPLY_TEMPERATURE_ENTITY),
                CONF_HEATING_SUPPLY_TARGET: self.current_config.get(CONF_HEATING_SUPPLY_TARGET, DEFAULTS[CONF_HEATING_SUPPLY_TARGET]),
                CONF_COOLING_SUPPLY_TARGET: self.current_config.get(CONF_COOLING_SUPPLY_TARGET, DEFAULTS[CONF_COOLING_SUPPLY_TARGET]),
                CONF_PUMP_START_DELAY_SECONDS: self.current_config.get(CONF_PUMP_START_DELAY_SECONDS, DEFAULTS[CONF_PUMP_START_DELAY_SECONDS]),
                CONF_HEATING_SOURCE_START_DELAY_SECONDS: self.current_config.get(CONF_HEATING_SOURCE_START_DELAY_SECONDS, DEFAULTS[CONF_HEATING_SOURCE_START_DELAY_SECONDS]),
                CONF_COOLING_SOURCE_START_DELAY_SECONDS: self.current_config.get(CONF_COOLING_SOURCE_START_DELAY_SECONDS, DEFAULTS[CONF_COOLING_SOURCE_START_DELAY_SECONDS]),
                CONF_MINIMUM_RUN_TIME_SECONDS: self.current_config.get(CONF_MINIMUM_RUN_TIME_SECONDS, DEFAULTS[CONF_MINIMUM_RUN_TIME_SECONDS]),
                CONF_PUMP_POST_RUN_SECONDS: self.current_config.get(CONF_PUMP_POST_RUN_SECONDS, DEFAULTS[CONF_PUMP_POST_RUN_SECONDS]),
                CONF_MINIMUM_OFF_TIME_SECONDS: self.current_config.get(CONF_MINIMUM_OFF_TIME_SECONDS, DEFAULTS[CONF_MINIMUM_OFF_TIME_SECONDS]),
            }
            return self.async_show_form(
                step_id="global_options",
                data_schema=vol.Schema({
                    vol.Required(CONF_GLOBAL_CO_MODE_ENTITY, default=current_global[CONF_GLOBAL_CO_MODE_ENTITY]): selector({
                        "entity": {
                            "multiple": False,
                            "domain": ["input_select", "input_boolean", "select"]
                        }
                    }),
                    vol.Optional(CONF_PACKING_MODE, default=current_global[CONF_PACKING_MODE]): selector({
                        "select": {"options": ["simultaneous", "staggered"]}
                    }),
                    vol.Optional(CONF_T_CYCLE_SECONDS, default=current_global[CONF_T_CYCLE_SECONDS]): selector({
                        "number": {"min": 120, "max": 3600, "mode": "box"}
                    }),
                    vol.Optional(CONF_T_CYCLE_MIN, default=current_global[CONF_T_CYCLE_MIN]): selector({
                        "number": {"min": 60, "max": 3600, "mode": "box"}
                    }),
                    vol.Optional(CONF_T_CYCLE_MAX, default=current_global[CONF_T_CYCLE_MAX]): selector({
                        "number": {"min": 120, "max": 7200, "mode": "box"}
                    }),
                    vol.Optional(CONF_RH_ALERT, default=current_global[CONF_RH_ALERT]): selector({
                        "number": {"min": 30, "max": 90, "step": 1, "mode": "box"}
                    }),
                    vol.Optional(CONF_RH_FAULT, default=current_global[CONF_RH_FAULT]): selector({
                        "number": {"min": 40, "max": 100, "step": 1, "mode": "box"}
                    }),
                    vol.Optional(CONF_DP_SAFETY_MARGIN, default=current_global[CONF_DP_SAFETY_MARGIN]): selector({
                        "number": {"min": 0.5, "max": 5, "step": 0.5, "mode": "box"}
                    }),
                    _optional_entity_field(CONF_HEATING_SOURCE_ENTITY, ["switch", "input_boolean"], current_global[CONF_HEATING_SOURCE_ENTITY])[0]:
                        _optional_entity_field(CONF_HEATING_SOURCE_ENTITY, ["switch", "input_boolean"], current_global[CONF_HEATING_SOURCE_ENTITY])[1],
                    _optional_entity_field(CONF_COOLING_SOURCE_ENTITY, ["switch", "input_boolean"], current_global[CONF_COOLING_SOURCE_ENTITY])[0]:
                        _optional_entity_field(CONF_COOLING_SOURCE_ENTITY, ["switch", "input_boolean"], current_global[CONF_COOLING_SOURCE_ENTITY])[1],
                    _optional_entity_field(CONF_CHANGEOVER_ENTITY, ["switch", "input_boolean"], current_global[CONF_CHANGEOVER_ENTITY])[0]:
                        _optional_entity_field(CONF_CHANGEOVER_ENTITY, ["switch", "input_boolean"], current_global[CONF_CHANGEOVER_ENTITY])[1],
                    _optional_entity_field(CONF_CIRCULATION_PUMP_ENTITY, ["switch", "input_boolean"], current_global[CONF_CIRCULATION_PUMP_ENTITY])[0]:
                        _optional_entity_field(CONF_CIRCULATION_PUMP_ENTITY, ["switch", "input_boolean"], current_global[CONF_CIRCULATION_PUMP_ENTITY])[1],
                    _optional_entity_field(CONF_TARGET_SUPPLY_TEMPERATURE_ENTITY, ["number", "input_number"], current_global[CONF_TARGET_SUPPLY_TEMPERATURE_ENTITY])[0]:
                        _optional_entity_field(CONF_TARGET_SUPPLY_TEMPERATURE_ENTITY, ["number", "input_number"], current_global[CONF_TARGET_SUPPLY_TEMPERATURE_ENTITY])[1],
                    vol.Optional(CONF_HEATING_SUPPLY_TARGET, default=current_global[CONF_HEATING_SUPPLY_TARGET]): selector({
                        "number": {"min": 10, "max": 60, "step": 0.5, "mode": "box"}
                    }),
                    vol.Optional(CONF_COOLING_SUPPLY_TARGET, default=current_global[CONF_COOLING_SUPPLY_TARGET]): selector({
                        "number": {"min": 5, "max": 30, "step": 0.5, "mode": "box"}
                    }),
                    vol.Optional(CONF_PUMP_START_DELAY_SECONDS, default=current_global[CONF_PUMP_START_DELAY_SECONDS]): selector({
                        "number": {"min": 0, "max": 600, "step": 1, "mode": "box"}
                    }),
                    vol.Optional(CONF_HEATING_SOURCE_START_DELAY_SECONDS, default=current_global[CONF_HEATING_SOURCE_START_DELAY_SECONDS]): selector({
                        "number": {"min": 0, "max": 900, "step": 1, "mode": "box"}
                    }),
                    vol.Optional(CONF_COOLING_SOURCE_START_DELAY_SECONDS, default=current_global[CONF_COOLING_SOURCE_START_DELAY_SECONDS]): selector({
                        "number": {"min": 0, "max": 900, "step": 1, "mode": "box"}
                    }),
                    vol.Optional(CONF_MINIMUM_RUN_TIME_SECONDS, default=current_global[CONF_MINIMUM_RUN_TIME_SECONDS]): selector({
                        "number": {"min": 0, "max": 7200, "step": 1, "mode": "box"}
                    }),
                    vol.Optional(CONF_PUMP_POST_RUN_SECONDS, default=current_global[CONF_PUMP_POST_RUN_SECONDS]): selector({
                        "number": {"min": 0, "max": 3600, "step": 1, "mode": "box"}
                    }),
                    vol.Optional(CONF_MINIMUM_OFF_TIME_SECONDS, default=current_global[CONF_MINIMUM_OFF_TIME_SECONDS]): selector({
                        "number": {"min": 0, "max": 7200, "step": 1, "mode": "box"}
                    })
                })
            )

        # Save global options
        options = self._config_entry.options.copy()
        options.update({
            CONF_GLOBAL_CO_MODE_ENTITY: user_input[CONF_GLOBAL_CO_MODE_ENTITY],
            CONF_PACKING_MODE: user_input[CONF_PACKING_MODE],
            CONF_T_CYCLE_SECONDS: user_input[CONF_T_CYCLE_SECONDS],
            CONF_T_CYCLE_MIN: user_input[CONF_T_CYCLE_MIN],
            CONF_T_CYCLE_MAX: user_input[CONF_T_CYCLE_MAX],
            CONF_RH_ALERT: user_input[CONF_RH_ALERT],
            CONF_RH_FAULT: user_input[CONF_RH_FAULT],
            CONF_DP_SAFETY_MARGIN: user_input[CONF_DP_SAFETY_MARGIN],
            CONF_HEATING_SOURCE_ENTITY: user_input.get(CONF_HEATING_SOURCE_ENTITY),
            CONF_COOLING_SOURCE_ENTITY: user_input.get(CONF_COOLING_SOURCE_ENTITY),
            CONF_CHANGEOVER_ENTITY: user_input.get(CONF_CHANGEOVER_ENTITY),
            CONF_CIRCULATION_PUMP_ENTITY: user_input.get(CONF_CIRCULATION_PUMP_ENTITY),
            CONF_TARGET_SUPPLY_TEMPERATURE_ENTITY: user_input.get(CONF_TARGET_SUPPLY_TEMPERATURE_ENTITY),
            CONF_HEATING_SUPPLY_TARGET: user_input[CONF_HEATING_SUPPLY_TARGET],
            CONF_COOLING_SUPPLY_TARGET: user_input[CONF_COOLING_SUPPLY_TARGET],
            CONF_PUMP_START_DELAY_SECONDS: user_input[CONF_PUMP_START_DELAY_SECONDS],
            CONF_HEATING_SOURCE_START_DELAY_SECONDS: user_input[CONF_HEATING_SOURCE_START_DELAY_SECONDS],
            CONF_COOLING_SOURCE_START_DELAY_SECONDS: user_input[CONF_COOLING_SOURCE_START_DELAY_SECONDS],
            CONF_MINIMUM_RUN_TIME_SECONDS: user_input[CONF_MINIMUM_RUN_TIME_SECONDS],
            CONF_PUMP_POST_RUN_SECONDS: user_input[CONF_PUMP_POST_RUN_SECONDS],
            CONF_MINIMUM_OFF_TIME_SECONDS: user_input[CONF_MINIMUM_OFF_TIME_SECONDS],
        })
        
        return self.async_create_entry(title="", data=options)

    async def async_step_zones_pick(self, user_input=None):
        """Handle zone selection."""
        if user_input is None:
            zones = self.current_config.get("zones", [])
            if not zones:
                return self.async_show_form(
                    step_id="zones_pick",
                    data_schema=vol.Schema({}),
                    errors={"base": "no_zones"}
                )
            
            # Create options for zone selection
            zone_options = {}
            for zone in zones:
                zone_id = zone.get(ZK_ID, "unknown")
                zone_name = zone.get(ZK_NAME, zone_id)
                zone_options[zone_id] = f"{zone_name} ({zone_id})"
            
            return self.async_show_form(
                step_id="zones_pick",
                data_schema=vol.Schema({
                    vol.Required("zone_id"): selector({
                        "select": {"options": list(zone_options.keys())}
                    })
                })
            )
        
        # Store selected zone ID and proceed to edit
        self.selected_zone_id = user_input["zone_id"]
        return await self.async_step_zone_edit()

    async def async_step_zone_edit(self, user_input=None):
        """Handle zone editing."""
        if not hasattr(self, 'selected_zone_id'):
            return await self.async_step_zones_pick()
        
        # Find the selected zone
        zones = self.current_config.get("zones", [])
        selected_zone = None
        for zone in zones:
            if zone.get(ZK_ID) == self.selected_zone_id:
                selected_zone = zone
                break
        
        if not selected_zone:
            return await self.async_step_zones_pick()
        
        if user_input is None:
            current_zone = self._get_zone_edit_defaults(selected_zone)
            return self.async_show_form(
                step_id="zone_edit",
                data_schema=self._build_zone_edit_schema(current_zone)
            )
        
        # Validate and save zone options
        errors = {}
        try:
            # Validate floor limits
            floor_limits = {}
            if user_input.get("heat_min") is not None and user_input.get("heat_min") != "":
                floor_limits["heat_min"] = float(user_input["heat_min"])
            if user_input.get("heat_max") is not None and user_input.get("heat_max") != "":
                floor_limits["heat_max"] = float(user_input["heat_max"])
            if user_input.get("cool_min") is not None and user_input.get("cool_min") != "":
                floor_limits["cool_min"] = float(user_input["cool_min"])
            if user_input.get("cool_max") is not None and user_input.get("cool_max") != "":
                floor_limits["cool_max"] = float(user_input["cool_max"])
            
            # Validate min <= max for each mode
            if "heat_min" in floor_limits and "heat_max" in floor_limits:
                if floor_limits["heat_min"] > floor_limits["heat_max"]:
                    errors["base"] = "invalid_floor_limits"
            if "cool_min" in floor_limits and "cool_max" in floor_limits:
                if floor_limits["cool_min"] > floor_limits["cool_max"]:
                    errors["base"] = "invalid_floor_limits"
            
            if errors:
                current_zone = self._get_zone_edit_defaults(selected_zone, user_input)
                return self.async_show_form(
                    step_id="zone_edit",
                    data_schema=self._build_zone_edit_schema(current_zone),
                    errors=errors
                )
            
            # Prepare zone update
            zone_update = {
                ZK_SUPPORT_MODE: user_input.get(ZK_SUPPORT_MODE, "BOTH"),
                ZK_SENSOR_AIR: user_input[ZK_SENSOR_AIR],
                ZK_SENSOR_RH: user_input[ZK_SENSOR_RH],
                ZK_SWITCH_ACT: user_input[ZK_SWITCH_ACT],
                ZK_OPEN_S: int(user_input.get(ZK_OPEN_S, 60)),
                ZK_CLOSE_S: int(user_input.get(ZK_CLOSE_S, 60)),
                ZK_ZONE_MIN_ON: int(user_input.get(ZK_ZONE_MIN_ON, 180)),
                ZK_ZONE_MIN_OFF: int(user_input.get(ZK_ZONE_MIN_OFF, 180)),
                ZK_SENSOR_FLOOR: user_input.get(ZK_SENSOR_FLOOR) or None,
                ZK_WINDOW_SWITCH: user_input.get(ZK_WINDOW_SWITCH) or None,
            }
            
            if floor_limits:
                zone_update[ZK_FLOOR_LIMITS] = floor_limits
            else:
                zone_update[ZK_FLOOR_LIMITS] = None
            
            # Persist a full merged zone list so restart does not depend on sparse overrides.
            options = self._config_entry.options.copy()
            zones = [dict(zone) for zone in self.current_config.get(CONF_ZONES, [])]
            zone_found = False
            for i, zone in enumerate(zones):
                if zone.get(ZK_ID) == self.selected_zone_id:
                    zones[i].update(zone_update)
                    zone_found = True
                    break

            if not zone_found:
                new_zone = {ZK_ID: self.selected_zone_id}
                new_zone.update(zone_update)
                zones.append(_coerce_zone_defaults(new_zone))

            options[CONF_ZONES] = [_coerce_zone_defaults(dict(zone)) for zone in zones]
            return self.async_create_entry(title="", data=options)
            
        except (ValueError, TypeError) as e:
            errors["base"] = "invalid_number"
            current_zone = self._get_zone_edit_defaults(selected_zone, user_input)
            return self.async_show_form(
                step_id="zone_edit",
                data_schema=self._build_zone_edit_schema(current_zone),
                errors=errors
            )

    async def async_step_finish(self, user_input=None):
        """Handle finish step."""
        return self.async_create_entry(title="", data=self._config_entry.options)
