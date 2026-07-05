# Virtual Climate

`Virtual Climate` is a custom Home Assistant integration for multi-zone underfloor heating and cooling control.

It exposes one climate entity per zone and coordinates slow thermal actuators with shared cycle logic, humidity protection, and optional floor temperature limits.

## Features

- Multi-zone virtual thermostats for UFH and similar hydronic systems
- Shared heat/cool cycle coordination across zones
- Global system mode with `HEAT`, `COOL`, and optional `OFF`
- Separate heating and cooling setpoints
- Optional floor sensor safety limits
- Optional humidity and dew point protection in cooling mode
- Per-zone coordinator diagnostics exposed in climate attributes
- `simultaneous` and staged `staggered` packing modes
- Dynamic cycle length between configured min/max bounds based on aggregated demand
- UI-based config flow with full JSON import, zone JSON import, or wizard mode
- Local-only custom integration under `custom_components/virtual_climate`

## Repository structure

```text
custom_components/virtual_climate/
├── __init__.py
├── climate.py
├── config_flow.py
├── const.py
├── helpers.py
├── hydronics.py
├── manifest.json
├── services.yaml
├── zone_manager.py
└── translations/
```

## HACS installation

1. Open HACS in Home Assistant.
2. Go to `Integrations`.
3. Add this repository as a `Custom repository`.
4. Select category `Integration`.
5. Install `Virtual Climate` and restart Home Assistant.

## Manual installation

1. Copy `custom_components/virtual_climate` into your Home Assistant `custom_components` directory.
2. Restart Home Assistant.
3. Add the integration from `Settings -> Devices & Services -> Add Integration`.

## Configuration

The integration supports:

- a global entity that indicates `HEAT`, `COOL`, or optionally `OFF`
- multiple zones with air sensor, RH sensor, and actuator
- optional floor sensor and window contact per zone
- optional per-zone floor safety limits and actuator timings

### Full JSON import

At integration setup you can now choose `Import full JSON` and paste one JSON
object containing both global settings and all zones.

Recommended structure:

```json
{
  "global": {
    "global_co_mode_entity": "input_select.hvac_mode",
    "packing_mode": "staggered",
    "t_cycle_seconds": 720,
    "t_cycle_min": 360,
    "t_cycle_max": 1440,
    "rh_alert": 60,
    "rh_fault": 70,
    "dp_safety_margin_c": 2.0,
    "heating_source_entity": "switch.heat_pump_heating",
    "cooling_source_entity": "switch.heat_pump_cooling",
    "circulation_pump_entity": "switch.floor_pump",
    "target_supply_temperature_entity": "input_number.supply_target",
    "heating_supply_target": 32.0,
    "cooling_supply_target": 18.0,
    "pump_start_delay_seconds": 0,
    "heating_source_start_delay_seconds": 30,
    "cooling_source_start_delay_seconds": 30,
    "minimum_run_time_seconds": 300,
    "pump_post_run_seconds": 120,
    "minimum_off_time_seconds": 180
  },
  "zones": [
    {
      "id": "living",
      "name": "Living",
      "sensor_air": "sensor.living_temperature",
      "sensor_rh": "sensor.living_humidity",
      "switch_actuator": "switch.ufh_living",
      "sensor_floor": "sensor.living_floor_temperature",
      "window_switch": "binary_sensor.living_window",
      "support_mode": "BOTH",
      "floor_limits": {
        "heat_min": 24,
        "heat_max": 29,
        "cool_min": 19,
        "cool_max": 24
      },
      "open_s": 60,
      "close_s": 60,
      "zone_min_on_s": 180,
      "zone_min_off_s": 180
    }
  ]
}
```

Notes:

- required global field: `global_co_mode_entity`
- required zone fields: `id`, `name`, `sensor_air`, `sensor_rh`, `switch_actuator`
- the importer still accepts the legacy format of a plain JSON array with zones only
- in `Options`, `Import JSON (replace)` replaces the existing integration config with the imported full JSON and clears old overrides
- after setup, `Options -> Export JSON` shows the current configuration in the same full import format

## Operating model

The integration uses a two-level control model:

- Global system mode: `HEAT`, `COOL`, or `OFF`
- Per-zone mode: `AUTO` or `OFF`

### Global mode helper

The global mode helper can behave in three ways:

- `input_boolean`: legacy behavior is preserved
  - `off` => `HEAT`
  - `on` => `COOL`
- `input_select` or `select` with `HEAT/COOL`
  - the system works only with those two modes
- `input_select` or `select` with `HEAT/COOL/OFF`
  - `OFF` disables the whole system

### What global `OFF` does

When the global helper is set to `OFF`:

- the coordinator stops planning new cycles
- all zone actuators are turned off
- zones in `AUTO` remain logically in `AUTO`, but they are inactive
- if you later return to `HEAT` or `COOL`, zones in `AUTO` resume normal operation

### Zone `AUTO/OFF`

Each virtual thermostat exposes:

- `AUTO`: the zone follows the global system mode
- `OFF`: manual override

If a user switches a zone from `AUTO` to `OFF`, that zone stays off even if the
global helper changes later. If the user switches the zone back to `AUTO` while
the global system is still `OFF`, the zone remains ready but inactive until the
global mode returns to `HEAT` or `COOL`.

## Global Plant Roadmap

The project will treat the hydronic plant as a separate global control layer on
top of the per-zone coordinator.

### MVP scope

The agreed MVP for global plant control is:

- `heating_source_entity` as a `switch`
- `cooling_source_entity` as a `switch`
- `circulation_pump_entity` as a `switch`
- optional `changeover_entity`
- `target_supply_temperature_entity` as a `number`
- supply control strategy based on fixed target values written to ESPHome

For the MVP, Home Assistant will command a target supply temperature and
ESPHome will perform the local mixing / regulation logic. Direct mixing valve
control from Home Assistant is intentionally out of scope for this first phase.

### Supported topology models

The design should support these global wiring patterns:

- `H + C`
  - separate heating and cooling calls
- `H + CO`
  - one shared source call plus a changeover selector
- `H + C + CO`
  - fully explicit heat, cool, and changeover outputs

If both heat and cool are represented by the same physical output, the same
entity may be reused by configuration, but this is treated as a deployment
detail rather than the primary UX model.

### MVP start/stop behavior

Plant start:

- start when any eligible zone in `AUTO` has demand
- no demand threshold in the MVP
- startup should be coordinated centrally and logged clearly for diagnostics

Plant stop:

- stop when no eligible zone in `AUTO` has demand
- respect a global minimum run time
- keep the circulation pump active for a configurable post-run time
- optionally respect a global minimum off time before restart

Global `OFF`:

- stop the active source after `minimum_run_time_seconds`
- keep the pump running for `pump_post_run_seconds`

### Global settings planned for MVP

- `pump_start_delay_seconds`
- `heating_source_start_delay_seconds`
- `cooling_source_start_delay_seconds`
- `minimum_run_time_seconds`
- `pump_post_run_seconds`
- `minimum_off_time_seconds`
- `heating_supply_target`
- `cooling_supply_target`

These settings are now part of the integration model and are intended to be
configured from the global settings step / options flow.

### Supply target strategy

The MVP uses fixed values:

- in `HEAT`, write `heating_supply_target` to the target supply entity
- in `COOL`, write `cooling_supply_target` to the target supply entity

This keeps heavy regulation logic inside ESPHome and allows the plant to remain
more autonomous when Home Assistant is unavailable.

### Changeover semantics in the MVP

If a `changeover_entity` is configured, the MVP assumes:

- `OFF` = heating
- `ON` = cooling

This matches the existing legacy boolean convention already used elsewhere in
the integration.

### Future phases after the MVP

The following items were discussed and should remain part of the roadmap even
if they are not implemented in the first global plant release:

- direct `mixing_valve_entity` control from Home Assistant
- advanced support for systems with separate `H`, `C`, and `CO` outputs
- dynamic supply target strategies based on `demand_ratio`
- richer start/stop sequencing and additional diagnostics
- more explicit modeling of standby vs active plant states

## Zone Coordinator

The coordinator is the central logic layer that translates all per-zone inputs
into actuator timing and global plant requests.

### Implemented now

- `packing_mode`
  - `simultaneous`: all eligible zones start together
  - `staggered`: zones are ordered by strongest demand and receive staggered
    start offsets within the cycle
- `cycle timing`
  - the effective cycle length is dynamically chosen between
    `t_cycle_min` and `t_cycle_max`
  - stronger aggregated demand results in a longer cycle
- `arbitration between zones`
  - zones are ranked by requested demand fraction
  - this rank is exposed for diagnostics
- `demand aggregation`
  - the coordinator computes an aggregated demand ratio and publishes it for
    global plant logic
- `RH / dew point protections`
  - cooling demand is derated near the RH alert threshold
  - cooling is blocked on RH fault
  - cooling is derated or blocked when dew point safety is violated
- `translation to global commands`
  - the aggregated demand is used to start or stop the global hydronic plant
  - the active system mode selects the plant source and fixed supply target

### Per-zone diagnostics

Each climate entity now exposes coordinator-oriented attributes that help
explain decisions in Home Assistant:

- `coordinator_status`
- `coordinator_phase`
- `coordinator_blocked_by`
- `coordinator_block_reasons`
- `coordinator_requested_fraction`
- `coordinator_requested_t_on_s`
- `coordinator_scheduled_t_on_s`
- `coordinator_start_offset_s`
- `coordinator_arbitration_rank`
- `coordinator_cycle_length_s`
- `coordinator_packing_mode`
- `coordinator_aggregated_demand_ratio`
- `plant_state`
- `plant_mode`

This is intended to make troubleshooting much easier when a zone has demand
but is not scheduled, is blocked by humidity / dew point / floor safety, or is
waiting behind other zones in staggered mode.

### Global diagnostics entities

The integration also exposes a small set of global diagnostic entities for
dashboarding, history, and automation:

- `binary_sensor.*_cycle_active`
- `sensor.*_system_mode`
- `sensor.*_coordinator_phase`
- `sensor.*_packing_mode`
- `sensor.*_aggregated_demand_ratio`
- `sensor.*_plant_state`
- `sensor.*_plant_mode`
- `sensor.*_scheduled_zones`
- `sensor.*_running_zones`
- `sensor.*_blocked_zones`
- `sensor.*_total_zones`
- `sensor.*_cycle_length_s`

## Development notes

The `dev/` folder contains helper scripts for local syncing and testing workflows.

## License

MIT
