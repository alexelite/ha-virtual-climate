from __future__ import annotations
from homeassistant.core import HomeAssistant, State
from .const import CONF_GLOBAL_CO_MODE_ENTITY

def dew_point_c(t_c: float, rh_percent: float) -> float:
    """Return dew point (°C) from air temperature (°C) and relative humidity (%).
    Magnus approximation (sufficient for HVAC control).
    """
    import math
    rh = max(0.1, min(100.0, rh_percent)) / 100.0
    a, b = 17.62, 243.12  # constants over water
    gamma = (a * t_c) / (b + t_c) + math.log(rh)
    return round((b * gamma) / (a - gamma), 1)

def get_state_float(hass: HomeAssistant, entity_id: str | None):
    if not entity_id:
        return None
    st: State | None = hass.states.get(entity_id)
    if not st or st.state in ("unknown", "unavailable", None):
        return None
    try:
        return float(st.state)
    except Exception:
        return None

def get_state_str(hass: HomeAssistant, entity_id: str | None):
    if not entity_id:
        return None
    st: State | None = hass.states.get(entity_id)
    return None if not st else st.state

def co_mode_from_entity(hass: HomeAssistant, data: dict) -> str:
    """Read the global HEAT/COOL/OFF mode from an HA helper."""
    ent = data.get(CONF_GLOBAL_CO_MODE_ENTITY)
    if not ent:
        return "HEAT"  # fallback
    st = hass.states.get(ent)
    if not st:
        return "HEAT"
    val = (st.state or "").lower()

    # Legacy input_boolean behavior: off=HEAT, on=COOL
    if ent.startswith("input_boolean."):
        if val in ("on", "true", "1"):
            return "COOL"
        return "HEAT"

    if val in ("off", "idle", "disabled"):
        return "OFF"
    if val in ("cool", "cooling"):
        return "COOL"
    if val in ("heat", "heating"):
        return "HEAT"
    if "cool" in val:
        return "COOL"
    if "off" in val:
        return "OFF"
    return "HEAT"
