# Adaptive heating

**Heating control with thermal memory** selects how zone heating demand becomes
actuator pulses. This is independent of the supply-temperature strategy.

| Strategy | Behavior |
| --- | --- |
| `legacy` | Existing proportional zone scheduling; default for existing and new entries |
| `observe` | Computes proposals and learns from actual activation without additional commands |
| `adaptive` | Uses bounded pulse accounting and initial PI control; prediction requires model eligibility |

Cooling retains its existing policy in all three modes.

## Validation limits

Adaptive heating is opt-in. In the recorded synthetic maintenance scenarios,
initial PI control reduced starts but increased temperature deficit in several
cases. The low-load scenario also increased severe overshoot. Full comfort
acceptance is not met; fewer starts do not compensate for worse comfort.

Read the [results and method](../development/observations/thermal-simulation-results.md)
before enabling adaptive control. These simulations do not establish suitable
parameters or improved comfort for a physical installation. `observe` allows
model proposals to be inspected while retaining existing commands.

## Configuration

Select the strategy in the integration options. Each zone can use `underfloor`
or `radiator`; the default is `underfloor`. Advanced entry parameters can be
overridden per zone. Import and export preserve these settings.

This fragment illustrates the thermal fields; retain the required global and
zone fields from the [full import format](../reference/configuration.md):

```json
{
  "global": {
    "heating_control_strategy": "observe",
    "thermal_parameters": {"comfort_below": 0.2, "comfort_above": 0.3}
  },
  "zones": [{
    "id": "zone_1",
    "thermal_profile": "underfloor",
    "thermal_parameters": {"supply_reference": 40}
  }]
}
```

[Parameter defaults and bounds](../reference/configuration.md#thermal-parameters)
are initial model assumptions, not measured physical properties.

## Model and pulse accounting

The model updates once a minute. Reported actuator activation enters a delay
queue, then a state with exponential persistence. The state is an indicator of
delayed thermal effect, not measured energy.

With valid circuit supply data and a reference temperature, activation is
weighted by the positive supply-room difference relative to reference-room,
clipped to 0–2. The configured heating supply target can provide the reference.
Without a valid reference or supply reading, the model uses unweighted activity
and reduced confidence. Reaching the supply target is not a prerequisite for
counting activation.

Until prediction is eligible, adaptive control uses existing proportional demand
plus a slow integral bounded to 0–1. Blocks, missing measurements, manual
intervention, suspected faults, and saturation constrain accumulation. Lowering
the setpoint clears incompatible integral and pulse balance. This module does
not write supply targets.

Requested activation time accumulates until a useful minimum pulse is possible.
The pulse assessment includes actuator opening, source delays, minimum run, and
post-run. Actual reported activation, including extensions, is debited. Balance
is bounded in both directions by the maximum cycle duration. If the minimum
pulse exceeds that maximum, the zone does not start and diagnostics explain why.
Window, floor, manual-off, and other protections retain priority.

## Learning and prediction

Identification searches bounded delay/persistence grids and fits nonnegative
thermal gain/loss. The first 70% of chronological samples fit the candidate;
the remaining data evaluate it without refitting. Eligibility requires at least:

- Seven valid days of observations.
- Three informative heating/pause sequences with sufficiently long segments.
- A 15% reduction in held-out thermal-rate mean squared error versus the initial profile.

Indistinguishable candidates or nearly constant activation do not justify
validation. An already accurate initial profile may not meet the improvement
threshold; the controller then remains on initial PI. Invalid data, gaps, manual
intervention, blocks, and suspected faults are excluded. Validation runs at most
once per six hours in the Home Assistant executor.

Eligible prediction evaluates demand from 0 to 100% in 5% steps, including delayed
effect and minimum pulses. Cost integrates squared deviations outside the comfort
band, penalizes deficit more heavily, and includes starts and demand variation.
Equal costs favor the previous demand.

## Persistence and diagnostics

Models and up to 21 days of observations persist per entry and zone in
`virtual_climate.<entry_id>.thermal_zones`, every 15 minutes and on unload.
Active history and pulse balance do not persist. After restart, prediction waits
for history covering delay plus three persistence constants; initial PI is
available meanwhile. Relevant sensor, actuator, profile, or parameter changes
invalidate the zone's experience.

The climate entity's `thermal_control` attributes expose proposals, actual
activation, demand, effect, confidence, prediction, pulse balance, decision
reason, and validation. `observe` keeps proposals distinct from real commands.
Returning to `legacy` restores the existing scheduling strategy.
