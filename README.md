# Virtual Climate

Virtual Climate is a custom Home Assistant integration for multi-zone hydronic
heating and cooling, including underfloor heating. It creates a virtual thermostat
for each zone and coordinates zone valves with a shared heating or cooling circuit.

Use it when your room sensors and zone actuator switches are already available
in Home Assistant and you need coordinated control across rooms. The integration
does not provide device firmware or directly regulate a mixing valve.

## What it does

- Separate heating and cooling setpoints for each zone.
- Shared cycles with simultaneous or staggered zone scheduling.
- Direct pump/source sequencing or a heating demand sent to an external controller.
- Window blocking, optional floor temperature limits, and humidity/dew-point
  protection during cooling.
- Constant supply targets or heating weather compensation, with optional curve
  learning and recovery boost.
- Diagnostics explaining zone demand, scheduling, protection, and circuit state.

Optional adaptive heating changes zone pulse scheduling. It is disabled by default;
[simulation results](docs/development/observations/thermal-simulation-results.md)
show increased temperature deficit in several maintenance scenarios. Read the
[adaptive heating guide](docs/features/adaptive-control.md) before enabling it.

## Requirements and installation

Each zone needs an air temperature sensor, a humidity sensor, and a controllable
actuator entity. A global mode helper selects heating, cooling, or off. Circuit
outputs depend on whether the integration or an external controller owns the
pump and source. External circuit control supports heating only.

Install through HACS as a custom integration repository, or copy
`custom_components/virtual_climate` into your Home Assistant configuration.
Then restart Home Assistant and add **Virtual Climate** from
**Settings → Devices & services → Add integration**.

Follow [Getting started](docs/getting-started.md) for prerequisites, installation,
and your first zone.

## Documentation

- [Configuration](docs/configuration.md): UI settings, import, and export.
- [Operation](docs/operation.md): modes, cycles, circuit responsibilities, and shutdown.
- [Troubleshooting](docs/troubleshooting.md): why a zone or circuit is not running.
- Optional features: [supply control](docs/features/supply-control.md),
  [external circuit](docs/features/external-circuit.md),
  [temperature fallback](docs/features/temperature-fallback.md), and
  [adaptive heating](docs/features/adaptive-control.md).
- Reference: [configuration keys](docs/reference/configuration.md),
  [diagnostics](docs/reference/diagnostics.md), and [glossary](GLOSSARY.md).
- [Changelog](CHANGELOG.md) and [contributing](CONTRIBUTING.md).

Report bugs and propose improvements in
[GitHub Issues](https://github.com/alexelite/ha-virtual-climate/issues).
Include the integration version and generic reproduction steps; remove personal
installation details from shared material.

## License

[MIT](LICENSE).
