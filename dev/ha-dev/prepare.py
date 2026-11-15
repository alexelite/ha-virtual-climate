"""Generate synthetic HA configuration and UI import payloads without dependencies."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEST = ROOT / "local/ha-dev"


def main():
    config = {
        "homeassistant": {"name": "Virtual Climate development"},
        "frontend": {}, "config": {}, "history": {}, "logbook": {},
        "recorder": {"purge_keep_days": 3}, "my": {},
        "input_select": {}, "input_number": {}, "input_boolean": {},
        "template": [{"sensor": [], "switch": []}],
    }
    templates = config["template"][0]
    payloads = {}
    for circuit in ("a", "b"):
        prefix = f"dev_{circuit}"
        config["input_select"][f"{prefix}_mode"] = {
            "options": ["OFF", "HEAT", "COOL"], "initial": "OFF"
        }
        sensors = {}
        for name, initial, unit, low, high in (
            ("outdoor", 5, "°C", -30, 40),
            ("supply", 30, "°C", 0, 90),
            ("return", 25, "°C", 0, 90),
            ("room_1", 20, "°C", 5, 35),
            ("room_2", 19, "°C", 5, 35),
            ("humidity", 45, "%", 0, 100),
        ):
            key = f"{prefix}_{name}"
            config["input_number"][key] = {
                "min": low, "max": high, "step": 0.1,
                "initial": initial, "unit_of_measurement": unit,
            }
            templates["sensor"].append({
                "name": key, "unique_id": key,
                "unit_of_measurement": unit,
                "device_class": "humidity" if unit == "%" else "temperature",
                "state": "{{ states('input_number." + key + "') }}",
            })
            sensors[name] = f"sensor.{key}"
        target = f"{prefix}_target"
        config["input_number"][target] = {"min": 5, "max": 90, "step": 0.1, "initial": 32}
        for role in ("valve_1", "valve_2", "pump", "source", "demand"):
            key = f"{prefix}_{role}"
            config["input_boolean"][key] = {"initial": False}
            templates["switch"].append({
                "name": key, "unique_id": key,
                "state": "{{ is_state('input_boolean." + key + "', 'on') }}",
                "turn_on": [{"action": "input_boolean.turn_on", "target": {"entity_id": f"input_boolean.{key}"}}],
                "turn_off": [{"action": "input_boolean.turn_off", "target": {"entity_id": f"input_boolean.{key}"}}],
            })
        global_config = {
            "global_co_mode_entity": f"input_select.{prefix}_mode",
            "circuit_control": "direct" if circuit == "a" else "external",
            "target_supply_temperature_entity": f"input_number.{target}",
            "supply_control": {
                "heating_strategy": "weather_compensated" if circuit == "a" else "constant",
                "outdoor_sensor": sensors["outdoor"],
                "supply_sensor": sensors["supply"], "return_sensor": sensors["return"],
                "outdoor_min": -15, "outdoor_max": 15,
                "supply_points": [40, 36, 32, 28, 24], "learning_mode": "off",
            },
        }
        if circuit == "a":
            global_config.update(heating_source_entity=f"switch.{prefix}_source", circulation_pump_entity=f"switch.{prefix}_pump")
        else:
            global_config["circuit_demand_entity"] = f"switch.{prefix}_demand"
        payloads[circuit] = {"global": global_config, "zones": [
            {"id": f"{prefix}_zone_{n}", "name": f"Circuit {circuit.upper()} zone {n}",
             "sensor_air": sensors[f"room_{n}"], "sensor_rh": sensors["humidity"],
             "switch_actuator": f"switch.{prefix}_valve_{n}", "support_mode": "HEAT"}
            for n in (1, 2)
        ]}
    (DEST / "config").mkdir(parents=True, exist_ok=True)
    # JSON is valid YAML; preserve an existing HA configuration on subsequent runs.
    path = DEST / "config/configuration.yaml"
    if not path.exists():
        path.write_text(json.dumps(config, indent=2) + "\n")
    for circuit, payload in payloads.items():
        (DEST / f"circuit-{circuit}.json").write_text(json.dumps(payload, indent=2) + "\n")
    print(f"Prepared synthetic configuration in {DEST}")


if __name__ == "__main__":
    main()
