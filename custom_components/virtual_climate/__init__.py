from __future__ import annotations
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import service
import logging

from .config_flow import get_current_config
from .const import (
    ZK_ID, ZK_SUPPORT_MODE, ZK_FLOOR_LIMITS, ZK_OPEN_S, ZK_CLOSE_S,
    ZK_ZONE_MIN_ON, ZK_ZONE_MIN_OFF, ZK_SENSOR_FLOOR, ZK_WINDOW_SWITCH
)

_LOGGER = logging.getLogger(__name__)

DOMAIN = "virtual_climate"
PLATFORMS = ["climate"]  # ensure climate platform is loaded

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the Virtual Climate integration from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    # Forward to platforms (creates entities, e.g., our VirtualThermostat)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Set up options update listener
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    
    # Register the update_zone service
    async def handle_update_zone(call: ServiceCall) -> None:
        """Handle the update_zone service call."""
        await async_update_zone(hass, entry, call.data)
    
    hass.services.async_register(
        DOMAIN,
        "update_zone",
        handle_update_zone,
        schema=None  # Will use the schema from services.yaml
    )
    
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the config entry and its platforms."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the integration when options are updated."""
    await hass.config_entries.async_reload(entry.entry_id)

async def async_update_zone(hass: HomeAssistant, entry: ConfigEntry, data: dict) -> None:
    """Update zone configuration at runtime."""
    zone_id = data.get("zone_id")
    if not zone_id:
        _LOGGER.error("zone_id is required")
        return
    
    # Get current config to find the zone
    current_config = get_current_config(entry)
    zones = current_config.get("zones", [])
    
    # Find the zone
    zone_found = False
    for zone in zones:
        if zone.get(ZK_ID) == zone_id:
            zone_found = True
            break
    
    if not zone_found:
        _LOGGER.error(f"Zone '{zone_id}' not found")
        return
    
    # Prepare zone update
    zone_update = {}
    fields_changed = []
    
    # Handle each optional field
    if "floor_limits" in data:
        floor_limits = data["floor_limits"]
        if floor_limits:
            # Validate floor limits
            if "heat_min" in floor_limits and "heat_max" in floor_limits:
                if floor_limits["heat_min"] > floor_limits["heat_max"]:
                    _LOGGER.error("Invalid floor limits: heat_min > heat_max")
                    return
            if "cool_min" in floor_limits and "cool_max" in floor_limits:
                if floor_limits["cool_min"] > floor_limits["cool_max"]:
                    _LOGGER.error("Invalid floor limits: cool_min > cool_max")
                    return
            zone_update[ZK_FLOOR_LIMITS] = floor_limits
            fields_changed.append("floor_limits")
        else:
            zone_update[ZK_FLOOR_LIMITS] = None
            fields_changed.append("floor_limits")
    
    if "open_s" in data:
        zone_update[ZK_OPEN_S] = int(data["open_s"])
        fields_changed.append("open_s")
    
    if "close_s" in data:
        zone_update[ZK_CLOSE_S] = int(data["close_s"])
        fields_changed.append("close_s")
    
    if "zone_min_on_s" in data:
        zone_update[ZK_ZONE_MIN_ON] = int(data["zone_min_on_s"])
        fields_changed.append("zone_min_on_s")
    
    if "zone_min_off_s" in data:
        zone_update[ZK_ZONE_MIN_OFF] = int(data["zone_min_off_s"])
        fields_changed.append("zone_min_off_s")
    
    if "sensor_floor" in data:
        zone_update[ZK_SENSOR_FLOOR] = data["sensor_floor"] or None
        fields_changed.append("sensor_floor")
    
    if "window_switch" in data:
        zone_update[ZK_WINDOW_SWITCH] = data["window_switch"] or None
        fields_changed.append("window_switch")
    
    if "support_mode" in data:
        zone_update[ZK_SUPPORT_MODE] = data["support_mode"]
        fields_changed.append("support_mode")
    
    if not zone_update:
        _LOGGER.warning("No valid fields to update")
        return
    
    # Update options
    options = entry.options.copy()
    if "zones" not in options:
        options["zones"] = []
    
    # Find and update the zone in options
    zone_updated = False
    for i, zone in enumerate(options["zones"]):
        if zone.get(ZK_ID) == zone_id:
            options["zones"][i].update(zone_update)
            zone_updated = True
            break
    
    if not zone_updated:
        # Create new zone entry in options
        new_zone = {ZK_ID: zone_id}
        new_zone.update(zone_update)
        options["zones"].append(new_zone)
    
    # Save the updated options
    hass.config_entries.async_update_entry(entry, options=options)
    
    # Fire event
    hass.bus.fire("virtual_climate/options_updated", {
        "zone_id": zone_id,
        "fields_changed": fields_changed
    })
    
    _LOGGER.info(f"Updated zone '{zone_id}' with fields: {fields_changed}")
