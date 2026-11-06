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

Omitted direct pump/source outputs mean that function is managed independently.
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
block a zone. Cooling is derated near the humidity alert threshold and blocked
on humidity fault or an unsafe dew-point condition. With a valid floor sensor, the coordinator blocks heating at `heat_max` and
cooling at `cool_min`. The other floor bounds are diagnostic conditions, not
additional interlocks or a demand to maintain floor temperature. A missing floor
sensor is reported and contributes no floor limit.

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
