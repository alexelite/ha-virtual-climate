# Supply temperature control

Open **Supply temperature control** during setup or in the integration's options.
Configure the target entity, constant targets, strategies, sensors, and limits.
Virtual Climate calculates and transmits a target; a local device regulates the
actual water temperature. See [circuit responsibilities](../operation.md#circuit-responsibilities).

## Choose a strategy

Heating supports `constant` and `weather_compensated`. Cooling supports `constant`
only. The constant heating target is also the fallback when outdoor data becomes
invalid during weather compensation. Existing configurations retain constant
targets until weather compensation is explicitly selected.

Weather compensation requires an outdoor sensor. Supply and return sensors are
optional and enable additional monitoring. The curve can be calculated without
a commanded source; curve learning, boost, and active response monitoring require
an operating-request context controlled by Virtual Climate.

In the direct profile, startup with weather compensation requires a configured
target output. In the external profile, a target output is optional and the
external controller may use its own target. A configured output must be available
and accept the write. See [External circuit](external-circuit.md).

## Configure the curve

The UI's curve object contains the outdoor interval and supply-point list. Between
2 and 50 points are evenly distributed across the interval. Targets interpolate
linearly; outside the interval, the end segment is extrapolated to the configured
supply limits. Curve learning pauses outside that interval.

This is a fragment of `global`; a full import also needs the mode helper and zones:

```json
{
  "target_supply_temperature_entity": "number.supply_target",
  "heating_supply_target": 32,
  "cooling_supply_target": 18,
  "supply_control": {
    "heating_strategy": "weather_compensated",
    "cooling_strategy": "constant",
    "outdoor_sensor": "sensor.outdoor_temperature",
    "supply_sensor": "sensor.supply_temperature",
    "return_sensor": "sensor.return_temperature",
    "outdoor_min": -15,
    "outdoor_max": 15,
    "supply_points": [40, 36, 32, 28, 24],
    "heating_min": 20,
    "heating_max": 45,
    "cooling_min": 5,
    "cooling_max": 30,
    "learning_mode": "off",
    "boost_enabled": true
  }
}
```

These values illustrate configuration; choose targets and limits appropriate for
your equipment. The [configuration reference](../reference/configuration.md)
contains the defaults and advanced observation/adjustment settings.

## Learning and recovery boost

| Learning mode | Effect |
| --- | --- |
| `off` | Base curve only; stored corrections are neither applied nor updated |
| `learn` | Applies corrections and permits reversible trials |
| `frozen` | Applies validated corrections without new trials |

Learning is off by default. It can trial a higher or lower correction at the
nearest outdoor point, using accumulated valid observation time across cycles.
At an exact midpoint, the colder outdoor point receives the observation. The
corrected heating curve cannot request lower water temperature as weather gets
colder; corrections that would invert it are limited.

Recovery boost is independent of learning. It uses eligible room deficits,
temperature trends, and reported activation. The largest valid zone need sets
the capped common boost. Normal pauses between slots do not erase boost while
room deficit remains. Boost is not converted into a learned correction.

Boost activation, setpoint changes, outdoor-condition changes, missing data, and
command errors interrupt trials and restore the validated correction. Learning
does not adjust the curve while boost is active. A suspected thermal fault
suspends learning for the common curve, retaining validated corrections.

Editing a base point resets that point's correction and experience. Changing
point count or outdoor interval resets all curve learning. The form describes
this effect before saving.

Validated corrections and experience persist separately for each entry. A trial
in progress is not resumed after restart; fresh observations are required.
Configuration exports omit learning history. The action
`virtual_climate.reset_supply_learning`, with `entry_id`, resets experience and
corrections while retaining the configured curve.

## Measurements and faults

Configuration temperatures are in °C and rates in °C/hour. Outdoor, supply, and
return measurements accept °C, °F, or K; target outputs accept °C or °F.
`unknown`, `unavailable`, non-finite values, and missing readings are invalid.
When sensor age checking is enabled, it uses the last report, falling back to
last update, rather than the last value change.

Room observations use the same sampled/filtered temperature as zone control.
Sampling is effectively at least 60 seconds; older 30-second settings use 60.
Observation windows and maximum gaps cover at least two effective intervals.
A filtered value cannot preserve an unavailable source.

Persistent insufficient room response, target deviation, or a large supply-return
difference can create diagnostics and a persistent notification. These findings
alone do not stop the source. Learning resumes after the configured period of
acceptable response; dismissing the notification does not clear the condition,
and automatic recovery does not override `frozen`.

Target writes wait for service completion with a ten-second timeout. A failed
required startup write prevents a new start. In operation, failure produces
retries and notification, without itself stopping the source. Device range and
units are checked before writing. Monitor calculated target, actual supply, and
learning status separately in [Diagnostics](../reference/diagnostics.md).

Observation thresholds are configurable starting values. Synthetic regression
tests verify policy and timing; they do not establish suitable calibration for
every physical circuit.
