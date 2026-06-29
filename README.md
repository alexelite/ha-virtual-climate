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
- UI-based config flow with wizard mode or JSON zone import
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

## Development notes

The `dev/` folder contains helper scripts for local syncing and testing workflows.

## License

MIT
