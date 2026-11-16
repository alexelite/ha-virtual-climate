# Operation

See [Control flows](reference/control-flows.md) for diagrams of zone demand,
supply-target dependencies, and reported feedback.

## Modes and demand

The global helper selects `HEAT`, `COOL`, or `OFF`. Each virtual thermostat uses
`AUTO` to follow that helper and `OFF` as a persistent manual override. Returning
the global helper to heating or cooling does not re-enable manually disabled
zones. Heating and cooling setpoints are separate.

An `input_select` or `select` provides explicit modes. The legacy `input_boolean`
convention is `off` = heating and `on` = cooling; it has no global off state.

Global `OFF` stops new cycles. Normal circuit shutdown respects minimum run and
post-run timing while eligible circulation paths remain available. Zones in
`AUTO` retain that logical mode and resume when the global mode becomes active.

Room error produces a requested heating/cooling fraction. In the default
`legacy` strategy, demand is proportional to room error. Protection blocks,
minimum timing, and available cycle time determine whether that demand can be
scheduled. [Adaptive heating](features/adaptive-control.md) optionally replaces
the heating pulse policy.

## Shared cycles

The coordinator selects a cycle length between its configured minimum and
maximum from aggregated demand and holds that length until the cycle ends.
`simultaneous` starts eligible slots together. `staggered` ranks zones by demand
and offsets their slots; offsets may overlap to preserve minimum on time.

Reported actuator transitions determine minimum on/off timing, with configured
opening/closing times included. A pulse is deferred when it cannot fit as a
useful minimum pulse. Adjacent full-cycle slots remain on across cycle boundaries.
Restart lockout affects scheduling while valid thermal demand remains visible.

## Circuit responsibilities

| Responsibility | Direct profile | External profile |
| --- | --- | --- |
| Zone valves and scheduling | Virtual Climate | Virtual Climate |
| Pump/source startup sequence | Virtual Climate for configured outputs | External controller |
| Circuit command | Pump, source, optional changeover | Heating demand |
| Supply target calculation/writing | Optional | Optional |
| Local mixing-valve regulation | Device | Device |
| Cooling | Existing direct configuration | Unsupported |
| Zone hold after shutdown | Direct pump post-run | External zone-hold timer |

Command entities can be device adapters rather than physical relays. Local
equipment protections can reject or interrupt commands. With multiple entries
sharing a source, use one owner of the physical output or an external demand
arbiter; entries must not independently fight over the same relay.

Omitted direct outputs mean that function is managed independently. The two
cases behave differently:

- **Source configured, no pump.** Virtual Climate sequences the source; the pump
  must circulate on its own.
- **Pump configured, no source at all (pump-only).** Virtual Climate starts the
  pump after a zone valve reports open and stops it with the normal post-run,
  in heating and in cooling. The source must produce supply water on its own:
  Virtual Climate does not start it, cannot tell whether it runs, and does not
  check water temperature. Supply-curve learning is not used. Saving this
  configuration in the options flow shows a notice explaining it.
- **Heating source configured, no cooling source or changeover.** Cooling remains
  unsupported; the pump does not start in cooling mode.

The integration does not create a substitute output. Device firmware, pins,
mixing-valve regulation, and hardware interlocks are outside this repository.

### Direct startup and shutdown

A source request waits for an eligible zone actuator to report `on` and complete
its opening time. Configured pump/source delays and minimum off time also apply.
If a supply target is required/configured for the startup path, its transmission
must succeed before the source starts.

During normal shutdown, eligible open zones remain open for minimum source run
time and pump post-run, then close. If a safety block removes the last valid
circulation path, the source and pump stop without waiting for normal shutdown.

During transfer, the previous valid path stays open until a replacement reports
`on` and completes opening. Opening commands precede closing commands. If the
replacement is not ready within its opening time plus 30 seconds, normal
shutdown uses the old valid path. Loss of the old path triggers protective stop.

A configured changeover switch uses `off` for heating and `on` for cooling.
Separate heating/cooling requests and a shared source with changeover are
supported by the direct sequence.

### External startup and shutdown

See [External circuit](features/external-circuit.md) for demand, timing alignment,
connection loss, and the heating-only restriction.

## Protection and reported state

Window contacts, manual off, floor limits, and humidity/dew-point conditions can
block a zone. See [Humidity and dew-point protection](#humidity-and-dew-point-protection)
for how cooling is reduced and stopped. If a zone has a humidity
sensor configured and it becomes unavailable, or no dew point can be derived,
that zone stops cooling with block reason `rh_unavailable` until the value
returns. A zone without a configured humidity sensor cools without humidity
protection. Heating does not depend on humidity. See
[ADR 0006](adr/0006-cooling-stops-on-humidity-loss.md). With a valid floor sensor, the coordinator blocks heating at `heat_max` and
cooling at `cool_min`. The other floor bounds are diagnostic conditions, not
additional interlocks or a demand to maintain floor temperature. A missing floor
sensor is reported and contributes no floor limit.

### Humidity and dew-point protection

These rules apply to each zone in cooling only. They use the zone's room
humidity and the dew point derived from room temperature and humidity.

- **Humidity alert.** From `rh_alert` up to `rh_fault`, the zone's cooling
  demand is reduced linearly: full demand at `rh_alert`, approaching half demand
  just below `rh_fault`. With the defaults of 60% and 70%, a zone at 65% receives
  75% of its normal cooling demand. The alert threshold reduces cooling; it is
  not only a notification.
- **Humidity fault.** At or above `rh_fault`, the zone stops cooling with block
  reason `rh_fault`. The block holds until humidity falls more than 5
  percentage points below `rh_fault` (65% with the defaults), so humidity that
  hovers around the threshold does not stop and restart the zone repeatedly.
  The block also clears when cooling ends or the humidity value disappears.
- **Dew-point margin.** The protected surface is the floor temperature when a
  valid floor sensor is configured, otherwise the room air temperature. The
  supply water temperature is not used. When the surface is above the dew point
  by less than `dp_safety_margin_c`, cooling demand is scaled by the remaining
  distance divided by the margin. At or below the dew point, the zone stops with
  block reason `dew_guard_lockout`.

Without a floor sensor, the comparison uses room air, which is normally much
warmer than a cooled floor. In that case the dew-point margin protects much less
than its value suggests; configure a floor sensor in zones that cool, and choose
cooling supply limits that stay above the expected dew point. Thresholds and
defaults are listed in the [configuration reference](reference/configuration.md#global-fields).

A command requests an output change. A reported switch `on` establishes software
feedback, not mechanical valve position, water flow, combustion, or delivered
heat. `hvac_action` and running diagnostics follow reported actuator state;
planned slots are shown separately. A valve held for circulation may remain
open after its own heating slot ends.

## Temperature and evaluation timing

Room measurements, contacts, protections, and thermal demand are evaluated
together every 60 seconds. Slot boundaries, opening times, and circuit delays
execute at their scheduled deadlines. Output feedback and explicit mode/setpoint
commands can request earlier reconciliation. There is no one-second planning loop.

The optional room filter is enabled by default and uses a 180-second time-based
EMA. Its weights depend on elapsed time, not message count. First readings
initialize directly. Invalid readings, source changes, toggling the filter,
and gaps over five minutes reset it. Raw sensor entities keep their original
reporting frequency; floor measurements and dew-point calculations use measured
data. A filtered value cannot keep an unavailable source eligible.

Numeric climate diagnostics are sampled at 60-second intervals to limit history
volume. Setpoint, mode, actuator, and protection changes bypass that interval,
as do sensor loss/recovery when detected. See [Diagnostics](reference/diagnostics.md).
