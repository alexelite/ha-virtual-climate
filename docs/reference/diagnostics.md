# Diagnostics reference

The integration exposes per-zone climate attributes and global diagnostic
entities. Entity IDs are assigned by Home Assistant; use their displayed names
rather than assuming a generated slug.

## Zone demand, scheduling, and feedback

| Attributes | Interpretation |
| --- | --- |
| `coordinator_status`, `coordinator_phase` | Scheduling state and coordinator phase |
| `coordinator_blocked_by`, `coordinator_block_reasons` | Why scheduling is blocked |
| `coordinator_requested_fraction`, `coordinator_requested_t_on_s` | Thermal request before scheduling constraints |
| `coordinator_scheduled_t_on_s`, `coordinator_start_offset_s` | Planned duration and offset |
| `coordinator_arbitration_rank` | Zone's demand rank |
| `coordinator_cycle_length_s`, `coordinator_packing_mode` | Current shared cycle and packing policy |
| `coordinator_aggregated_demand_ratio` | Shared thermal demand |
| `coordinator_scheduled_running` | Whether the current slot calls for activation |
| `coordinator_running`, `hvac_action` | Reported actuator activation |
| `actuator_state`, `actuator_commanded_state`, `actuator_mismatch` | Feedback, intended output, and disagreement |
| `plant_state`, `plant_mode` | Shared circuit sequence state and mode |
| `plant_flow_hold`, `plant_flow_hold_reason` | Valve retained for `handover` or `stopping` |
| `floor_limit_state` | Floor condition; `no_floor_sensor` means floor limits do not participate |

Command, schedule, reported output, and physical operation have different meanings;
see [Operation](../operation.md#protection-and-reported-state).

## Measurements and optional models

| Attributes | Interpretation |
| --- | --- |
| `t_air`, `t_air_raw` | Control/display room temperature and raw room reading |
| `temperature_source` | `measured`, `instance_fallback`, or `unavailable` |
| `control_temperature` | Temperature used internally for zone demand |
| `fallback_donor_count` | Distinct measured donors for fallback |
| `fallback_limited_by_plant_demand` | Fallback constrained by measured-zone circuit demand |
| `thermal_control` | Adaptive/observe demand, delayed effect, prediction, confidence, pulse balance, decision, and validation |

`t_air_raw` is available live but excluded from Recorder. Numeric attributes are
sampled to limit history volume; important state changes bypass that sampling.

## Global entities

The global set includes **Cycle active**, **System mode**, **Coordinator phase**,
**Packing mode**, **Aggregated demand ratio**, **Plant state**, **Plant mode**,
**Scheduled zones**, **Running zones**, **Blocked zones**, **Total zones**, and
**Cycle length**.

Running zones includes `scheduled_running_zones`, `actuator_mismatches`, and
`unavailable_actuators` attributes.

Detailed circuit capabilities and reported-state diagnostics are internal and
are not exposed as sensor attributes.

Supply diagnostics distinguish **Supply curve target**, **Learned supply
correction**, **Supply trial adjustment**, **Recovery boost**, and **Supply target**.
Separate entities expose outdoor, actual supply, return, supply-return difference,
strategy, learning status, and the zone determining the target.

Learning-status attributes include curve points, experience, trials, zone trends,
recent events, faults, and command errors. Compare final target and actual supply
in history; an in-progress trial is not a validated correction.

The `virtual_climate/hydronics_demand` event remains available once per cycle.
High-frequency zone status/schedule diagnostics are passed internally rather
than emitted as separate bus events.
