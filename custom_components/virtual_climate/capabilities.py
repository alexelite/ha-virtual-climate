"""Explicit circuit ownership and independent feature requirements."""
from math import isfinite

CIRCUIT_DEFAULTS = dict(circuit_control="direct", circuit_demand_entity=None,
                        circuit_state_entity=None, external_start_delay_seconds=0,
                        external_post_run_seconds=120)


def validate_circuit(config):
    profile = config.get("circuit_control", "direct")
    if profile not in ("direct", "external"):
        raise ValueError("Unknown circuit control profile")
    demand = config.get("circuit_demand_entity")
    if profile == "external":
        if (not isinstance(demand, str) or demand.count(".") != 1
                or not demand.split(".")[1] or demand.split(".")[0] not in ("switch", "input_boolean")):
            raise ValueError("External circuit requires a demand entity")
        if any(config.get(k) for k in ("circulation_pump_entity", "heating_source_entity",
                                       "cooling_source_entity", "changeover_entity")):
            raise ValueError("External circuit cannot also own direct pump/source/changeover outputs")
    elif demand or config.get("circuit_state_entity"):
        raise ValueError("Circuit demand and state require external control")
    for key in ("external_start_delay_seconds", "external_post_run_seconds"):
        value = config.get(key, CIRCUIT_DEFAULTS[key])
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or not isfinite(value) or value < 0 or value != int(value)):
            raise ValueError("Invalid circuit timing: " + key)


def circuit_capabilities(config, *, outdoor_valid=False, supply_valid=False, operating=False):
    external = config.get("circuit_control", "direct") == "external"
    supply = config.get("supply_control") or {}
    return dict(external_circuit=external and bool(config.get("circuit_demand_entity")),
                direct_pump=not external and bool(config.get("circulation_pump_entity")),
                direct_source=not external and bool(config.get("heating_source_entity") or config.get("cooling_source_entity")),
                cooling=not external and bool(config.get("cooling_source_entity") or
                    (config.get("heating_source_entity") and config.get("changeover_entity"))),
                supply_target=bool(config.get("target_supply_temperature_entity")),
                weather_compensation=outdoor_valid and supply.get("heating_strategy") == "weather_compensated",
                supply_verification=supply_valid and operating,
                circuit_state=external and bool(config.get("circuit_state_entity")),
                external_zone_hold=external and config.get("external_post_run_seconds", 120) > 0)
