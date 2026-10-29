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
├── supply_control.py
├── supply_regulator.py
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

The source starts only after an actuator reports `on` and its configured
`open_s` has elapsed. Configured pump/source delays and minimum off time also
apply. During normal shutdown, already-open eligible zones stay open through
the source's minimum run time and pump post-run, then close. Window, floor,
humidity and manual-OFF protections take precedence: if the last valid path
is lost, source and pump stop without waiting for normal shutdown delays.

During a planned transfer between zones, the previous valid circulation path
stays open until a replacement reports `on` and its `open_s` has elapsed.
This also applies across cycle boundaries. Open commands are submitted before
close commands. A replacement has its opening time plus 30 seconds to become
ready; otherwise the source shuts down normally using the existing valid path,
including minimum run time and pump post-run. A safety block or actual loss
of the last open path still causes an immediate protective stop.

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

These settings are now part of the integration model and are intended to be
configured from the global settings step / options flow. Constant heating and
cooling targets and the target supply entity are configured in
`Supply temperature control`, together with strategies, sensors and limits.
The heating constant target also serves as the weather-compensation fallback.

### Supply target strategy

The MVP uses fixed values:

- in `HEAT`, write `heating_supply_target` to the target supply entity
- in `COOL`, write `cooling_supply_target` to the target supply entity

This keeps heavy regulation logic inside ESPHome and allows the plant to remain
more autonomous when Home Assistant is unavailable.

### Weather compensation

Heating can use a configurable multipoint weather curve, optional learned
corrections and a separate recovery boost. Cooling currently uses a constant
target. Existing entries keep their fixed strategy until explicitly configured.
The target is refreshed during operation, not only at source startup.

Open `Options -> Supply temperature control`, or import `global.supply_control`.
See [temperature fallback](docs/temperature-fallback.md) for optional heating of zones with missing room sensors.

See [configuration, diagnostics and calibration](docs/supply-control.md) for a
complete example and the experimental timing defaults. Learning is off by default;
its initial thresholds need calibration and validation in the real installation.

The terminology and decisions are recorded in:

- [Domain glossary](GLOSSARY.md)
- [Supply target calculation, local regulation and monitoring](docs/adr/0001-supply-target-and-local-regulation.md)
- [Per-mode strategies and function requirements](docs/adr/0002-supply-strategies-and-capability-requirements.md)
- [Transparent learning and temporary correction](docs/adr/0003-transparent-learning-and-temporary-correction.md)

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
  - the duration stays fixed until that cycle ends
  - the one-second coordinator tick reconciles actuator states; there are no
    per-zone delayed callbacks that can outlive a cycle
  - adjacent full-cycle slots remain on across a cycle boundary
  - actual `on`/`off` state transitions determine minimum on/off timing;
    actuator opening/closing times are added to these minimums
  - staggered offsets may overlap to preserve minimum on time; a zone waiting
    for restart is deferred when a full minimum pulse cannot fit in the cycle
- `arbitration between zones`
  - zones are ranked by requested demand fraction
  - this rank is exposed for diagnostics
- `demand aggregation`
  - the coordinator computes an aggregated demand ratio and publishes it for
    global plant logic
  - restart lockout affects scheduling, while thermal demand remains visible
  - zero is published only when there is no valid thermal demand (or global OFF)
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

Climate temperature, humidity and numeric coordinator diagnostics are sampled
at 60-second intervals to reduce state/history volume. Changes to setpoints,
operating modes, actuator state and protection status bypass this interval,
as do sensor loss and recovery when detected at the next evaluation. Room
measurements, window contacts, protection conditions and thermal demand are
evaluated together every 60 seconds. Slot boundaries, valve opening times and
plant delays execute at their own deadlines; there is no one-second planning
loop. Explicit setpoint/mode commands can request an earlier evaluation.

Each zone has **Smooth room temperature (3 minutes)** in its options, enabled
by default (`temperature_filter_enabled` in zone JSON or `update_zone`). It
applies a time-based EMA to room air temperature for both climate display and
demand, and for the room observations used by supply compensation. Its time
constant is 180 seconds; weights use actual elapsed time and never the count
of sensor messages. First readings initialize directly; invalid readings clear
the filter, as do source changes, enabling/disabling, and gaps over 5 minutes.
Dedicated sensor entities retain their raw values and reporting frequency.
`t_air_raw` is available in live climate attributes but excluded from Recorder.
Floor measurements and dew-point calculations continue to use measured data.

Zone status and schedule diagnostics are passed directly in memory instead of
emitting `virtual_climate/zone_status` and `virtual_climate/zone_schedule` bus
events. The existing `virtual_climate/hydronics_demand` event remains available
once per cycle. Unchanged diagnostics do not notify entities again. Existing
history is unaffected; these changes reduce future records.

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
- `coordinator_scheduled_running`
- `actuator_state`
- `actuator_commanded_state`
- `actuator_mismatch`
- `plant_flow_hold`
- `plant_flow_hold_reason`

This is intended to make troubleshooting much easier when a zone has demand
but is not scheduled, is blocked by humidity / dew point / floor safety, or is
waiting behind other zones in staggered mode.

`coordinator_running` and `hvac_action` use the reported actuator switch state.
`coordinator_scheduled_running` describes the planned interval. Switch `on`
confirms the electrical output; it does not measure valve position or water
flow. `plant_flow_hold` explains a valve held open for circulation;
`plant_flow_hold_reason` distinguishes `handover` from `stopping`.
`coordinator_phase` describes the coordinator independently of `plant_state`.

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

The running-zones sensor also exposes `scheduled_running_zones`,
`actuator_mismatches` and `unavailable_actuators` as attributes.

Optional floor and window selectors can be cleared in zone options. An empty
selector is saved explicitly as `null` and remains empty after reload. Zones
without a configured floor sensor report `no_floor_sensor`; their floor limits
do not participate in control.

## Development notes

The `dev/` folder contains helper scripts for local syncing and testing workflows.

Run the regression suite with Python 3.10 or newer:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-test.txt
.venv/bin/python -m unittest discover -s tests -v
```

Tests execute production coordinator, options-flow and climate logic with
controlled time and mocked HA services/state storage. Schema validation uses
real Voluptuous. They cover slot timing, cycle continuity, restart lockout,
source/pump sequencing, reported actuator states and clearing optional fields.
They also cover delayed zone handover, valve opening time, failed replacement,
loss of the old path and a two-hour plant simulation with delayed feedback.
Live ESPHome feedback and full HA integration loading require verification on
the running installation. Python-code updates require a HA Core restart;
`dev/sync.sh` performs this unless passed `--no-restart`.

### Deploy over SSH

The SSH alias `ha` must reach a host with Python 3, rsync, Docker, the HA CLI
and access to the running `homeassistant` container and its configuration.
Use the same test environment as above:

```bash
bash dev/sync.sh --dry-run --host ha --test-python .venv/bin/python
bash dev/sync.sh --host ha --test-python .venv/bin/python
```

The script packages an immutable component snapshot, runs regression tests,
backs up the installed code and this integration's persisted configuration,
then uploads to a separate staging directory. SHA-256 hashes, Python/JSON
syntax and imports in the actual HA Python environment must pass before the
live directory is replaced. It checks HA configuration, restarts Core and
waits for a new container process with a responding API. Check integration
loading, actuator feedback and logs through HA after deployment; API readiness
alone does not establish that every integration loaded successfully.

Backups are retained under `<config>/virtual_climate_backups/<backup-id>/`.
The integration configuration snapshot is private reference material; restoring
code never overwrites HA's internal `.storage`. A failed configuration check
or restart restores the previous component code automatically. Deployment
metadata is also saved locally in ignored `local/deployments/`.

To restore code from a deployment's backup (with another backup and restart):

```bash
bash dev/sync.sh --host ha --rollback BACKUP_ID
```

`--config-root PATH` overrides configuration-directory detection.
`--no-restart` leaves an installation pending a Core restart; currently loaded
Python code continues to run until then. `--dry-run` runs tests and shows a
read-only rsync comparison without creating remote backups or changing settings.

## License

MIT
