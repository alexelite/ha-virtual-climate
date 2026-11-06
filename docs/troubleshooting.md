# Troubleshooting

Start with the zone's climate attributes and the global diagnostic entities.
[Diagnostics](reference/diagnostics.md) distinguishes demand, schedule, reported
activation, and circuit state.

| Symptom | Check |
| --- | --- |
| Zone does not request heating | Global mode, zone `AUTO/OFF`, supported mode, room sensor, and heating setpoint |
| Demand exists but valve is off | Block reason, scheduled slot, staggered offset, minimum off time, and whether a minimum pulse fits |
| Valve is on but source is off | Opening time, startup delays, minimum off time, target-write error, and circuit profile |
| Valve stays on after its slot | `plant_flow_hold` and its reason: transfer or normal shutdown |
| Cooling does not start | External control does not support cooling; check direct outputs, humidity, dew point, and floor protection |
| Floor sensor is absent | `no_floor_sensor` means no floor limit participates; configure a valid sensor if required |
| Displayed temperature is smoother than the sensor | The zone's room-temperature filter; raw sensor entities are unchanged |
| Supply learning does not progress | Learning mode, valid observations, boost, fallback, suspected faults, outdoor interval, and trial status |
| Adaptive prediction is unavailable | Valid days, informative sequences, held-out improvement, and rebuilt history after restart |
| Options change interrupts heating | Saving options reloads the entry and applies shutdown/restart timing |

## Supply target errors

Check that the configured target entity is available, writable, and accepts the
requested unit and range. A failed target write can prevent a new start; during
operation it causes retries and diagnostic notification rather than, by itself,
an automatic source stop. A successful write and achieved water temperature
are separate conditions. See [Supply control](features/supply-control.md).

## Missing room measurements

Missing/invalid measurements do not become valid through filtering. Optional
[temperature fallback](features/temperature-fallback.md) allows limited heating
alongside measured zones; it does not repair the sensor or establish the room's
actual temperature.

## Reporting a problem

Open a [GitHub issue](https://github.com/alexelite/ha-virtual-climate/issues) with:

- Integration version and Home Assistant version.
- Expected behavior, observed behavior, and generic reproduction steps.
- Relevant diagnostic values and timestamped logs, with personal details removed.
- Circuit profile and applicable timing settings using generic entity names.

Keep raw installation exports and identifiable reports outside the repository.
For contributor validation, see [Testing](development/testing.md).
