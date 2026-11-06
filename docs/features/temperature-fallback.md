# Temperature fallback

**Heat zones with missing sensors using the instance median** is an opt-in,
heating-only setting in **Global Settings**. Its JSON key is
`global.instance_temperature_fallback`; the default is `false`.

## Behavior

A zone without its own valid room measurement can use the median of valid primary
room measurements from heating-compatible zones in the same configuration entry.
For an even number of measurements, the middle pair is averaged. Shared sensors
are counted once. Estimated values are never donors; manually disabled zones may
still contribute actual measurements.

The climate entity's measured temperature remains unavailable. Its setpoint
remains editable and controls requested actuator opening using the fallback
value internally. A median of 21°C produces heating demand at a 22°C setpoint
and none at 20°C; it does not establish the affected room's actual temperature.

Only measured zones can request the source, determine cycle length, and contribute
to aggregated demand. Fallback zones join their active windows without shifting
measured-zone slots or extending the source request. Minimum timing and safe
shutdown holds remain applicable, so the requested fallback duration is not
guaranteed to be fully delivered.

If no valid donor or measured-zone heating demand exists, fallback does not start
the circuit. Entries are independent. Normal measured control resumes at the
next evaluation after the primary sensor recovers.

## Limitations

Use this as a temporary measure while repairing a sensor. Other rooms' median can
overheat or underheat the affected room. Manual off, window, floor, and actuator
availability protections remain effective; fallback is unavailable in cooling.

Internal donor observations older than 120 seconds are rejected, and primary
sources are reread at each thermal evaluation. A frozen numeric value at the
source does not prove that a device is healthy; devices must report unavailability.

Fallback zones do not participate in recovery boost or room-response monitoring.
Active fallback suspends common supply-curve learning and interrupts a trial;
validated corrections are retained. Measured rooms may still determine boost.

Diagnostics include `temperature_source`, `control_temperature`,
`fallback_donor_count`, and `fallback_limited_by_plant_demand`; see
[Diagnostics](../reference/diagnostics.md).
