# Configuration

Open the integration's options in **Settings → Devices & services** to edit an
existing configuration. Each configuration entry has its own zones, circuit
entities, and learning state.

## Virtual Climate panel

Open **Virtual Climate** in the sidebar. The panel shares one sidebar entry
across configuration entries; use the instance selector to switch circuits.
Entry-specific URLs can be bookmarked.

**Operation** provides basic room setpoint and AUTO/OFF controls and reported
circuit values. **Diagnostics** shows supply-target contributions separately;
administrators can also consult the saved base curve and the complete **Saved
configuration** without opening an editor: instance and circuit settings, the
effective supply settings, and each zone, as stored. Empty optional settings are
omitted.
These pages do not edit integration configuration. Reported output activation
does not confirm physical operation; see [Operation](operation.md#protection-and-reported-state).

Administrators can open **Settings → Supply temperature control** to edit supply
strategies, sensors, target output, constant targets, limits, base-curve points,
learning mode and recovery boost. Curve fields appear when heating uses weather
compensation; cooling settings are omitted for the heating-only external profile.
The editor preserves hidden values and advanced supply tuning.

Administrators can open **Zone settings** to edit one zone at a time: name,
supported modes, temperature smoothing, room sensor, actuator switch, humidity
sensor, floor sensor, window contact, valve timings, minimum on/off times and
floor limits (10–40 °C). Zone ID, thermal profile, thermal parameters and keys
not shown are preserved and remain editable only in the options flow. Other zones
are unaffected.

Global and circuit settings, thermal control, adding or removing zones, and
JSON import/export remain available only in the integration's options flow.

Both editors work the same way. Edits remain local until **Review changes**,
followed by **Apply changes**.
The review lists changed values, learning resets and the reload impact described
[below](#saving-and-reload). Discarding edits restores the last configuration
loaded into the editor. Applying changes affects only the selected entry.
If another session or options flow saves first, reload the saved configuration
before editing again; stale edits are rejected rather than overwriting it.

The graph compares the draft base curve with the saved curve. A constant
strategy appears as a horizontal line. Graph temperatures are in °C. The graph
does not command equipment or include live learned corrections, trials or boost;
consult their separate values in **Diagnostics**. Point count and outdoor
interval changes reset all curve learning; changing a base point resets that
point's learning. See [Supply control](features/supply-control.md#learning-and-recovery-boost).

## Global Settings

Select the global mode helper and the `direct` or `external` circuit profile.
Configure circuit outputs, minimum run/off times, and startup/shutdown delays
according to [Operation](operation.md). External mode uses separate demand and
zone-hold settings described in [External circuit](features/external-circuit.md).

Choose `simultaneous` packing to start eligible zone slots together, or
`staggered` to offset them by demand rank. Cycle minimum and maximum bound the
cycle length selected from measured-zone demand. Humidity thresholds and the
dew-point margin apply during cooling.

If a circulation pump is configured without any heating or cooling source,
saving shows a notice before the change is stored: Virtual Climate will command
only the pump, and the source must operate independently. See
[Operation](operation.md#circuit-responsibilities).

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
