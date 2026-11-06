# Configuration

Open the integration's options in **Settings → Devices & services** to edit an
existing configuration. Each configuration entry has its own zones, circuit
entities, and learning state.

## Global Settings

Select the global mode helper and the `direct` or `external` circuit profile.
Configure circuit outputs, minimum run/off times, and startup/shutdown delays
according to [Operation](operation.md). External mode uses separate demand and
zone-hold settings described in [External circuit](features/external-circuit.md).

Choose `simultaneous` packing to start eligible zone slots together, or
`staggered` to offset them by demand rank. Cycle minimum and maximum bound the
cycle length selected from measured-zone demand. Humidity thresholds and the
dew-point margin apply during cooling.

Temperature fallback is an explicit heating-only option; read its
[limitations](features/temperature-fallback.md) before enabling it.

## Edit Zones

Select a zone to edit sensors, actuator, supported modes, window contact, floor
limits, and actuator/minimum on/off times. With a valid floor sensor, `heat_max`
blocks heating and `cool_min` blocks cooling. `heat_min` and `cool_max` report
floor conditions but do not force room demand or add coordinator interlocks.
Floor limits are distinct from room setpoints.

**Smooth room temperature (3 minutes)** enables a time-based room-temperature
filter. It affects display and control without changing the original sensor.
The [operation guide](operation.md#temperature-and-evaluation-timing) describes
sampling and reset behavior.

Optional floor and window fields can be cleared. Exported configuration preserves
cleared values as `null`. Adaptive profiles and parameters are described in
[Adaptive heating](features/adaptive-control.md).

## Supply temperature control

Set constant heating/cooling targets and the entity receiving the target here.
Heating can use weather compensation. Curve learning and recovery boost are
separate controls; see [Supply control](features/supply-control.md).

## Heating control with thermal memory

Select `legacy`, `observe`, or `adaptive`. These strategies concern zone heating
pulses, independently of the supply-temperature strategy. Cooling retains the
existing scheduling policy. Read [Adaptive heating](features/adaptive-control.md)
for the validation limits and model eligibility rules.

## Import and export

Initial setup accepts a full JSON object with `global` and `zones`, or a legacy
zones-only array. Full configuration is preferable for reproducible setup.

**Export JSON** returns the current configuration in the full import format.
**Import JSON (replace)** replaces the configuration and zone list and clears
previous overrides. Preserve an export before replacement. Learning history is
stored separately and is not included in the export.

See the [configuration reference](reference/configuration.md) for a complete
minimal JSON example and supported keys.

## Saving and reload

Saving options reloads the configuration entry. Shutdown can stop circuit outputs
before valid demand resumes with the applicable startup and minimum-off delays.
For external control, unloading can wait for the configured zone-hold interval.
Do not treat editing options as an interruption-free operation.
