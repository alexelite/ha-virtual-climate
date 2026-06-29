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
    ZK_OPEN_S: 60,
    ZK_CLOSE_S: 60,
    ZK_ZONE_MIN_ON: 180,
    ZK_ZONE_MIN_OFF: 180,
}


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


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow with dual path: wizard steps OR JSON import for faster setup."""
    VERSION = 1

    def __init__(self) -> None:
        self._global: Dict[str, Any] = {}
        self._zones: List[Dict[str, Any]] = []

    # ---------- Step 1: Global options ----------
    async def async_step_user(self, user_input=None):
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({
                    vol.Required(CONF_GLOBAL_CO_MODE_ENTITY): selector({
                        "entity": {
                            "multiple": False,
                            "domain": ["input_select", "input_boolean"]
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
                    })
                })
            )
        self._global = dict(user_input)
        return await self.async_step_choose_method()

    # ---------- Step 2: Choose method ----------
    async def async_step_choose_method(self, user_input=None):
        """Menu to pick JSON import or zone-by-zone wizard."""
        if user_input is None:
            return self.async_show_menu(
                step_id="choose_method",
                menu_options=["zones_json", "zone_wizard", "finish"]
            )
        # No direct POST expected here; clicking a menu item routes to that step id.

    # ---------- Path A: JSON import ----------
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
            parsed = json.loads(zones_text)
            if not isinstance(parsed, list) or not parsed:
                raise ValueError("JSON must be a non-empty array")

            for z in parsed:
                if not isinstance(z, dict):
                    raise ValueError("Each zone must be an object")
                for req in (ZK_ID, ZK_NAME, ZK_SENSOR_AIR, ZK_SENSOR_RH, ZK_SWITCH_ACT):
                    if not z.get(req):
                        raise ValueError(f"Missing required field '{req}' in a zone")
                _validate_zone_id_unique(self._zones, z[ZK_ID])
                self._zones.append(_coerce_zone_defaults(z))

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
            zones_data = {zone.get(ZK_ID): zone for zone in entry.data.get("zones", [])}
            zones_options = {zone.get(ZK_ID): zone for zone in entry.options.get("zones", [])}
            # Merge each zone's options over its data
            merged_zones = []
            for zone_id, zone_data in zones_data.items():
                zone_options = zones_options.get(zone_id, {})
                merged_zone = zone_data.copy()
                merged_zone.update(zone_options)
                merged_zones.append(merged_zone)
            data["zones"] = merged_zones
    return data


class VirtualClimateOptionsFlow(config_entries.OptionsFlow):
    """Options flow for Virtual Climate integration."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        """Initialize options flow."""
        self.config_entry = config_entry
        self.current_config = get_current_config(config_entry)

    async def async_step_init(self, user_input=None):
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_menu(
                step_id="init",
                menu_options=["global_options", "zones_pick", "finish"]
            )
        return await getattr(self, f"async_step_{user_input}")()

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
            }
            return self.async_show_form(
                step_id="global_options",
                data_schema=vol.Schema({
                    vol.Required(CONF_GLOBAL_CO_MODE_ENTITY, default=current_global[CONF_GLOBAL_CO_MODE_ENTITY]): selector({
                        "entity": {
                            "multiple": False,
                            "domain": ["input_select", "input_boolean"]
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
                    })
                })
            )

        # Save global options
        options = self.config_entry.options.copy()
        options.update({
            CONF_GLOBAL_CO_MODE_ENTITY: user_input[CONF_GLOBAL_CO_MODE_ENTITY],
            CONF_PACKING_MODE: user_input[CONF_PACKING_MODE],
            CONF_T_CYCLE_SECONDS: user_input[CONF_T_CYCLE_SECONDS],
            CONF_T_CYCLE_MIN: user_input[CONF_T_CYCLE_MIN],
            CONF_T_CYCLE_MAX: user_input[CONF_T_CYCLE_MAX],
            CONF_RH_ALERT: user_input[CONF_RH_ALERT],
            CONF_RH_FAULT: user_input[CONF_RH_FAULT],
            CONF_DP_SAFETY_MARGIN: user_input[CONF_DP_SAFETY_MARGIN],
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
            # Pre-fill with current zone values
            current_zone = {
                ZK_SUPPORT_MODE: selected_zone.get(ZK_SUPPORT_MODE, "BOTH"),
                ZK_OPEN_S: selected_zone.get(ZK_OPEN_S, DEFAULTS.get(ZK_OPEN_S, 60)),
                ZK_CLOSE_S: selected_zone.get(ZK_CLOSE_S, DEFAULTS.get(ZK_CLOSE_S, 60)),
                ZK_ZONE_MIN_ON: selected_zone.get(ZK_ZONE_MIN_ON, DEFAULTS.get(ZK_ZONE_MIN_ON, 180)),
                ZK_ZONE_MIN_OFF: selected_zone.get(ZK_ZONE_MIN_OFF, DEFAULTS.get(ZK_ZONE_MIN_OFF, 180)),
                ZK_SENSOR_FLOOR: selected_zone.get(ZK_SENSOR_FLOOR) or "",
                ZK_WINDOW_SWITCH: selected_zone.get(ZK_WINDOW_SWITCH) or "",
            }
            
            # Handle floor_limits
            floor_limits = selected_zone.get(ZK_FLOOR_LIMITS, {})
            if floor_limits:
                current_zone.update({
                    "heat_min": floor_limits.get("heat_min", ""),
                    "heat_max": floor_limits.get("heat_max", ""),
                    "cool_min": floor_limits.get("cool_min", ""),
                    "cool_max": floor_limits.get("cool_max", ""),
                })
            else:
                current_zone.update({
                    "heat_min": "",
                    "heat_max": "",
                    "cool_min": "",
                    "cool_max": "",
                })
            
            return self.async_show_form(
                step_id="zone_edit",
                data_schema=vol.Schema({
                    vol.Optional(ZK_SUPPORT_MODE, default=current_zone[ZK_SUPPORT_MODE]): selector({
                        "select": {"options": ["HEAT", "COOL", "BOTH"]}
                    }),
                    vol.Optional("heat_min", default=current_zone["heat_min"]): selector({
                        "number": {"min": 10, "max": 40, "step": 0.5, "mode": "box"}
                    }),
                    vol.Optional("heat_max", default=current_zone["heat_max"]): selector({
                        "number": {"min": 10, "max": 40, "step": 0.5, "mode": "box"}
                    }),
                    vol.Optional("cool_min", default=current_zone["cool_min"]): selector({
                        "number": {"min": 10, "max": 40, "step": 0.5, "mode": "box"}
                    }),
                    vol.Optional("cool_max", default=current_zone["cool_max"]): selector({
                        "number": {"min": 10, "max": 40, "step": 0.5, "mode": "box"}
                    }),
                    vol.Optional(ZK_OPEN_S, default=current_zone[ZK_OPEN_S]): selector({
                        "number": {"min": 0, "max": 600, "mode": "box"}
                    }),
                    vol.Optional(ZK_CLOSE_S, default=current_zone[ZK_CLOSE_S]): selector({
                        "number": {"min": 0, "max": 600, "mode": "box"}
                    }),
                    vol.Optional(ZK_ZONE_MIN_ON, default=current_zone[ZK_ZONE_MIN_ON]): selector({
                        "number": {"min": 0, "max": 3600, "mode": "box"}
                    }),
                    vol.Optional(ZK_ZONE_MIN_OFF, default=current_zone[ZK_ZONE_MIN_OFF]): selector({
                        "number": {"min": 0, "max": 3600, "mode": "box"}
                    }),
                    vol.Optional(ZK_SENSOR_FLOOR, default=current_zone[ZK_SENSOR_FLOOR]): selector({
                        "entity": {"domain": "sensor"}
                    }),
                    vol.Optional(ZK_WINDOW_SWITCH, default=current_zone[ZK_WINDOW_SWITCH]): selector({
                        "entity": {"domain": "binary_sensor"}
                    }),
                })
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
                return self.async_show_form(
                    step_id="zone_edit",
                    data_schema=vol.Schema({
                        vol.Optional(ZK_SUPPORT_MODE, default=user_input.get(ZK_SUPPORT_MODE, "BOTH")): selector({
                            "select": {"options": ["HEAT", "COOL", "BOTH"]}
                        }),
                        vol.Optional("heat_min", default=user_input.get("heat_min", "")): selector({
                            "number": {"min": 10, "max": 40, "step": 0.5, "mode": "box"}
                        }),
                        vol.Optional("heat_max", default=user_input.get("heat_max", "")): selector({
                            "number": {"min": 10, "max": 40, "step": 0.5, "mode": "box"}
                        }),
                        vol.Optional("cool_min", default=user_input.get("cool_min", "")): selector({
                            "number": {"min": 10, "max": 40, "step": 0.5, "mode": "box"}
                        }),
                        vol.Optional("cool_max", default=user_input.get("cool_max", "")): selector({
                            "number": {"min": 10, "max": 40, "step": 0.5, "mode": "box"}
                        }),
                        vol.Optional(ZK_OPEN_S, default=user_input.get(ZK_OPEN_S, 60)): selector({
                            "number": {"min": 0, "max": 600, "mode": "box"}
                        }),
                        vol.Optional(ZK_CLOSE_S, default=user_input.get(ZK_CLOSE_S, 60)): selector({
                            "number": {"min": 0, "max": 600, "mode": "box"}
                        }),
                        vol.Optional(ZK_ZONE_MIN_ON, default=user_input.get(ZK_ZONE_MIN_ON, 180)): selector({
                            "number": {"min": 0, "max": 3600, "mode": "box"}
                        }),
                        vol.Optional(ZK_ZONE_MIN_OFF, default=user_input.get(ZK_ZONE_MIN_OFF, 180)): selector({
                            "number": {"min": 0, "max": 3600, "mode": "box"}
                        }),
                        vol.Optional(ZK_SENSOR_FLOOR, default=user_input.get(ZK_SENSOR_FLOOR, "")): selector({
                            "entity": {"domain": "sensor"}
                        }),
                        vol.Optional(ZK_WINDOW_SWITCH, default=user_input.get(ZK_WINDOW_SWITCH, "")): selector({
                            "entity": {"domain": "binary_sensor"}
                        }),
                    }),
                    errors=errors
                )
            
            # Prepare zone update
            zone_update = {
                ZK_SUPPORT_MODE: user_input.get(ZK_SUPPORT_MODE, "BOTH"),
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
            
            # Update options
            options = self.config_entry.options.copy()
            if "zones" not in options:
                options["zones"] = []
            
            # Find and update the zone in options
            zone_found = False
            for i, zone in enumerate(options["zones"]):
                if zone.get(ZK_ID) == self.selected_zone_id:
                    options["zones"][i].update(zone_update)
                    zone_found = True
                    break
            
            if not zone_found:
                # Create new zone entry in options
                new_zone = {ZK_ID: self.selected_zone_id}
                new_zone.update(zone_update)
                options["zones"].append(new_zone)
            
            return self.async_create_entry(title="", data=options)
            
        except (ValueError, TypeError) as e:
            errors["base"] = "invalid_number"
            return self.async_show_form(
                step_id="zone_edit",
                data_schema=vol.Schema({
                    vol.Optional(ZK_SUPPORT_MODE, default=user_input.get(ZK_SUPPORT_MODE, "BOTH")): selector({
                        "select": {"options": ["HEAT", "COOL", "BOTH"]}
                    }),
                    vol.Optional("heat_min", default=user_input.get("heat_min", "")): selector({
                        "number": {"min": 10, "max": 40, "step": 0.5, "mode": "box"}
                    }),
                    vol.Optional("heat_max", default=user_input.get("heat_max", "")): selector({
                        "number": {"min": 10, "max": 40, "step": 0.5, "mode": "box"}
                    }),
                    vol.Optional("cool_min", default=user_input.get("cool_min", "")): selector({
                        "number": {"min": 10, "max": 40, "step": 0.5, "mode": "box"}
                    }),
                    vol.Optional("cool_max", default=user_input.get("cool_max", "")): selector({
                        "number": {"min": 10, "max": 40, "step": 0.5, "mode": "box"}
                    }),
                    vol.Optional(ZK_OPEN_S, default=user_input.get(ZK_OPEN_S, 60)): selector({
                        "number": {"min": 0, "max": 600, "mode": "box"}
                    }),
                    vol.Optional(ZK_CLOSE_S, default=user_input.get(ZK_CLOSE_S, 60)): selector({
                        "number": {"min": 0, "max": 600, "mode": "box"}
                    }),
                    vol.Optional(ZK_ZONE_MIN_ON, default=user_input.get(ZK_ZONE_MIN_ON, 180)): selector({
                        "number": {"min": 0, "max": 3600, "mode": "box"}
                    }),
                    vol.Optional(ZK_ZONE_MIN_OFF, default=user_input.get(ZK_ZONE_MIN_OFF, 180)): selector({
                        "number": {"min": 0, "max": 3600, "mode": "box"}
                    }),
                    vol.Optional(ZK_SENSOR_FLOOR, default=user_input.get(ZK_SENSOR_FLOOR, "")): selector({
                        "entity": {"domain": "sensor"}
                    }),
                    vol.Optional(ZK_WINDOW_SWITCH, default=user_input.get(ZK_WINDOW_SWITCH, "")): selector({
                        "entity": {"domain": "binary_sensor"}
                    }),
                }),
                errors=errors
            )

    async def async_step_finish(self, user_input=None):
        """Handle finish step."""
        return self.async_create_entry(title="", data=self.config_entry.options)
