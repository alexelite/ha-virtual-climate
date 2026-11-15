"""Shared panel registration and entry-scoped configuration commands."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

try:
    import probatio as schema
except ImportError:  # Home Assistant releases before the schema migration.
    import voluptuous as schema

from homeassistant.auth.permissions.const import POLICY_READ
from homeassistant.components import panel_custom, websocket_api
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er

from .config_flow import (
    DEFAULTS, SUPPLY_BASIC_KEYS, SUPPLY_CURVE_KEYS, _build_export_payload,
    _coerce_zone_defaults, build_supply_options, get_current_config,
)
from .supply_control import effective_supply_config

DOMAIN = "virtual_climate"
SUPPLY_KEYS = SUPPLY_BASIC_KEYS + SUPPLY_CURVE_KEYS
OUTPUT_KEYS = ("target_supply_temperature_entity", "heating_supply_target", "cooling_supply_target")
EDITABLE_KEYS = OUTPUT_KEYS + SUPPLY_KEYS


def revision(entry):
    """Cover all entry data/options, including edits made outside the panel."""
    value = json.dumps([dict(entry.data), dict(entry.options)], sort_keys=True, allow_nan=False)
    return sha256(value.encode()).hexdigest()


def settings(config):
    supply = effective_supply_config(config.get("supply_control"))
    return {**{key: config.get(key, DEFAULTS[key]) for key in OUTPUT_KEYS},
            **{key: deepcopy(supply[key]) for key in SUPPLY_KEYS}}


def prepare_change(entry, changes):
    """Use the options-flow validator and preserve settings outside this editor."""
    if not isinstance(changes, dict) or set(changes) - set(EDITABLE_KEYS):
        raise ValueError("Unknown supply setting")
    current = get_current_config(entry)
    before = settings(current)
    proposed = {**before, **deepcopy(changes)}
    supply = effective_supply_config(current.get("supply_control"))
    supply.update({key: proposed[key] for key in SUPPLY_KEYS})
    form = {key: proposed[key] for key in OUTPUT_KEYS}
    form.update({key: supply[key] for key in SUPPLY_BASIC_KEYS})
    form["curve"] = {key: supply[key] for key in SUPPLY_CURVE_KEYS}
    form["tuning"] = {key: value for key, value in supply.items() if key not in SUPPLY_KEYS}
    options = build_supply_options(current, entry.options, form)
    after = settings({**current, **options})
    differences = [{"key": key, "before": before[key], "after": after[key]}
                   for key in EDITABLE_KEYS if before[key] != after[key]]
    geometry = any(before[key] != after[key] for key in ("outdoor_min", "outdoor_max"))
    geometry = geometry or len(before["supply_points"]) != len(after["supply_points"])
    reset_points = [] if geometry else [i + 1 for i, (a, b) in enumerate(
        zip(before["supply_points"], after["supply_points"])) if a != b]
    return options, {"changes": differences, "learning_reset": "all" if geometry else "points" if reset_points else "none",
                     "reset_points": reset_points, "settings": after, "reload_required": bool(differences)}


ZONE_ENTITY_FIELDS = {  # key: (allowed domains, required)
    "sensor_air": (("sensor",), True),
    "switch_actuator": (("switch", "group"), True),
    "sensor_rh": (("sensor",), False),
    "sensor_floor": (("sensor",), False),
    "window_switch": (("binary_sensor",), False),
}
ZONE_TIMING_FIELDS = {"open_s": 600, "close_s": 600, "zone_min_on_s": 3600, "zone_min_off_s": 3600}
FLOOR_FIELDS = ("heat_min", "heat_max", "cool_min", "cool_max")
ZONE_KEYS = ("name", "support_mode", "temperature_filter_enabled", *ZONE_ENTITY_FIELDS,
             *ZONE_TIMING_FIELDS, *("floor_" + key for key in FLOOR_FIELDS))


def zone_settings(zone):
    """Flatten one stored zone into the fields the panel edits."""
    floor = zone.get("floor_limits") or {}
    result = {key: zone.get(key) for key in ZONE_KEYS if not key.startswith("floor_")}
    result["temperature_filter_enabled"] = zone.get("temperature_filter_enabled", True)
    result["support_mode"] = zone.get("support_mode", "BOTH")
    for key in ZONE_TIMING_FIELDS:
        result[key] = zone.get(key, DEFAULTS[key])
    result.update({"floor_" + key: floor.get(key) for key in FLOOR_FIELDS})
    return result


def _number(value, low, high, label, integer=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value != value or not low <= value <= high:
        raise ValueError(f"{label} must be a number between {low} and {high}")
    if integer and value != int(value):
        raise ValueError(f"{label} must be a whole number")
    return int(value) if integer else float(value)


def normalize_zone_settings(values):
    """Validate a complete panel zone draft; returns stored zone fields."""
    if not isinstance(values, dict) or set(values) - set(ZONE_KEYS):
        raise ValueError("Unknown zone setting")
    name = values.get("name")
    if not isinstance(name, str) or not name.strip() or len(name) > 64:
        raise ValueError("Zone name must be 1-64 characters")
    if values.get("support_mode") not in ("HEAT", "COOL", "BOTH"):
        raise ValueError("Invalid zone support mode")
    if not isinstance(values.get("temperature_filter_enabled"), bool):
        raise ValueError("temperature_filter_enabled must be boolean")
    zone = {"name": name.strip(), "support_mode": values["support_mode"],
            "temperature_filter_enabled": values["temperature_filter_enabled"]}
    for key, (domains, required) in ZONE_ENTITY_FIELDS.items():
        entity = values.get(key) or None
        if entity is None:
            if required:
                raise ValueError(f"{key} is required")
        elif (not isinstance(entity, str) or entity.count(".") != 1
              or entity.split(".")[0] not in domains or not entity.split(".")[1]):
            raise ValueError(f"{key} must be a {' or '.join(domains)} entity")
        zone[key] = entity
    for key, high in ZONE_TIMING_FIELDS.items():
        zone[key] = _number(values.get(key), 0, high, key, integer=True)
    floor = {}
    for key in FLOOR_FIELDS:
        value = values.get("floor_" + key)
        if value is not None:
            floor[key] = _number(value, 10, 40, "floor_" + key)
    for mode in ("heat", "cool"):
        if floor.get(mode + "_min", -1) > floor.get(mode + "_max", 99):
            raise ValueError(f"Floor {mode} minimum is above maximum")
    zone["floor_limits"] = floor or None
    return zone


def prepare_zone_change(entry, zone_id, changes):
    """Apply a panel zone draft to a copy of the options, preserving other zone keys."""
    current = get_current_config(entry)
    zones = [deepcopy(zone) for zone in current.get("zones", [])]
    index = next((i for i, zone in enumerate(zones) if zone.get("id") == zone_id), None)
    if index is None:
        raise KeyError("Zone not found")
    before = zone_settings(zones[index])
    if not isinstance(changes, dict) or set(changes) - set(ZONE_KEYS):
        raise ValueError("Unknown zone setting")
    zones[index].update(normalize_zone_settings({**before, **deepcopy(changes)}))
    zones = [_coerce_zone_defaults(zone) for zone in zones]
    after = zone_settings(zones[index])
    differences = [{"key": key, "before": before[key], "after": after[key]}
                   for key in ZONE_KEYS if before[key] != after[key]]
    options = {**deepcopy(dict(entry.options)), "zones": zones}
    return options, {"changes": differences, "settings": after, "reload_required": bool(differences),
                     "learning_reset": "none", "reset_points": []}


def full_config(config):
    """Read-only view of every stored setting, in export layout."""
    payload = _build_export_payload(config)
    payload["global"]["supply_control"] = effective_supply_config(config.get("supply_control"))
    return payload


async def async_setup_panel(hass):
    """Register once for the integration; entry reloads do not replace the panel."""
    directory = Path(__file__).parent / "frontend"
    def resource_version():
        return sha256((directory / "panel.js").read_bytes()).hexdigest()[:16]

    version = await hass.async_add_executor_job(resource_version)
    await hass.http.async_register_static_paths([
        StaticPathConfig("/virtual_climate_static", str(directory), False)
    ])
    await panel_custom.async_register_panel(
        hass, frontend_url_path="virtual-climate", webcomponent_name="virtual-climate-panel",
        sidebar_title="Virtual Climate", sidebar_icon="mdi:thermostat",
        module_url=f"/virtual_climate_static/panel.js?v={version}",
    )
    for handler in (ws_entries, ws_settings, ws_validate, ws_save, ws_config,
                    ws_zone_validate, ws_zone_save):
        websocket_api.async_register_command(hass, handler)


def _entry(hass, connection, msg):
    entry = hass.config_entries.async_get_entry(msg["entry_id"])
    if entry is None or entry.domain != DOMAIN:
        connection.send_error(msg["id"], "not_found", "Configuration entry not found")
        return None
    return entry


@websocket_api.websocket_command({"type": "virtual_climate/panel/entries"})
@callback
def ws_entries(hass, connection, msg):
    registry = er.async_get(hass)
    result = []
    for entry in hass.config_entries.async_entries(DOMAIN):
        entities = [entity for entity in er.async_entries_for_config_entry(registry, entry.entry_id)
                    if not entity.disabled and connection.user.permissions.check_entity(entity.entity_id, POLICY_READ)]
        if not entities and not connection.user.is_admin:
            continue
        result.append({"entry_id": entry.entry_id, "title": entry.title, "state": entry.state.value,
                       "entities": [{"entity_id": e.entity_id,
                                     "key": e.unique_id.removeprefix(entry.entry_id + "_")}
                                    for e in entities]})
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command({"type": "virtual_climate/panel/settings", schema.Required("entry_id"): str})
@websocket_api.require_admin
@callback
def ws_settings(hass, connection, msg):
    if (entry := _entry(hass, connection, msg)) is None:
        return
    config = get_current_config(entry)
    connection.send_result(msg["id"], {"revision": revision(entry), "settings": settings(config),
                                       "profile": config.get("circuit_control", "direct")})


def _change(hass, connection, msg, *, save, prepare=None):
    if (entry := _entry(hass, connection, msg)) is None:
        return
    if msg["revision"] != revision(entry):
        connection.send_error(msg["id"], "conflict", "Configuration changed. Reload the saved configuration before editing again.")
        return
    if save and entry.state.value != "loaded":
        connection.send_error(msg["id"], "not_ready", "The instance is reloading or unavailable. Wait until it is loaded before applying changes.")
        return
    try:
        options, result = (prepare or prepare_change)(entry, msg["changes"])
    except KeyError as error:
        connection.send_error(msg["id"], "not_found", str(error.args[0] if error.args else error))
        return
    except (ValueError, TypeError, OverflowError) as error:
        connection.send_error(msg["id"], "invalid_settings", str(error))
        return
    # No await between the revision check and update: another save cannot interleave.
    if save and result["changes"]:
        hass.config_entries.async_update_entry(entry, options=options)
    connection.send_result(msg["id"], {**result, "revision": revision(entry)})


_CHANGE_SCHEMA = {schema.Required("entry_id"): str, schema.Required("revision"): str,
                  schema.Required("changes"): dict}


@websocket_api.websocket_command({"type": "virtual_climate/panel/validate", **_CHANGE_SCHEMA})
@websocket_api.require_admin
@callback
def ws_validate(hass, connection, msg):
    _change(hass, connection, msg, save=False)


@websocket_api.websocket_command({"type": "virtual_climate/panel/save", **_CHANGE_SCHEMA})
@websocket_api.require_admin
@callback
def ws_save(hass, connection, msg):
    _change(hass, connection, msg, save=True)


@websocket_api.websocket_command({"type": "virtual_climate/panel/config", schema.Required("entry_id"): str})
@websocket_api.require_admin
@callback
def ws_config(hass, connection, msg):
    if (entry := _entry(hass, connection, msg)) is None:
        return
    config = get_current_config(entry)
    connection.send_result(msg["id"], {
        "revision": revision(entry), "config": full_config(config),
        "zones": [{"id": zone.get("id"), "settings": zone_settings(zone)} for zone in config.get("zones", [])]})


_ZONE_SCHEMA = {**_CHANGE_SCHEMA, schema.Required("zone_id"): str}


def _zone_change(hass, connection, msg, *, save):
    _change(hass, connection, msg, save=save,
            prepare=lambda entry, changes: prepare_zone_change(entry, msg["zone_id"], changes))


@websocket_api.websocket_command({"type": "virtual_climate/panel/zone_validate", **_ZONE_SCHEMA})
@websocket_api.require_admin
@callback
def ws_zone_validate(hass, connection, msg):
    _zone_change(hass, connection, msg, save=False)


@websocket_api.websocket_command({"type": "virtual_climate/panel/zone_save", **_ZONE_SCHEMA})
@websocket_api.require_admin
@callback
def ws_zone_save(hass, connection, msg):
    _zone_change(hass, connection, msg, save=True)
