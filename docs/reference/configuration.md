# Configuration reference

UI workflows are described in [Configuration](../configuration.md). Temperature
settings use °C, rates use °C/hour, and timing keys ending in `_s` or `_seconds`
use seconds. Entity IDs below are generic examples; replace them before import.

## Full import format

This minimal heating-only example uses independently managed circulation/source
and leaves supply target writing unconfigured. Add circuit outputs or select
external control according to your equipment; this example alone does not
command a heat source.

```json
{
  "global": {
    "global_co_mode_entity": "input_select.system_mode",
    "circuit_control": "direct"
  },
  "zones": [
    {
      "id": "zone_1",
      "name": "Zone 1",
      "sensor_air": "sensor.zone_1_temperature",
      "sensor_rh": "sensor.zone_1_humidity",
      "switch_actuator": "switch.zone_1_actuator",
      "support_mode": "HEAT"
    }
  ]
}
```

The required global field is `global_co_mode_entity`. Every zone requires `id`,
`name`, `sensor_air`, `sensor_rh`, and `switch_actuator`. Zone IDs must be unique.
A legacy nonempty zones-only array is also accepted; a full object records the
global configuration explicitly.

## Global fields

| Key | Default | Meaning |
| --- | --- | --- |
| `global_co_mode_entity` | Required | `input_select`, `select`, or legacy `input_boolean` mode helper |
| `circuit_control` | `direct` | `direct` or heating-only `external` |
| `heating_source_entity` | `null` | Direct heating request switch |
| `cooling_source_entity` | `null` | Direct cooling request switch |
| `circulation_pump_entity` | `null` | Direct circulation command |
| `changeover_entity` | `null` | Direct mode output: off heating, on cooling |
| `circuit_demand_entity` | `null` | External heating demand: `switch` or `input_boolean` |
| `circuit_state_entity` | `null` | Optional external state sensor |
| `external_start_delay_seconds` | 0 | Additional wait before external demand |
| `external_post_run_seconds` | 120 | Valid zone hold after external demand withdrawal |
| `pump_start_delay_seconds` | 0 | Direct pump startup delay |
| `heating_source_start_delay_seconds` | 30 | Direct heating source delay |
| `cooling_source_start_delay_seconds` | 30 | Direct cooling source delay |
| `minimum_run_time_seconds` | 300 | Minimum source-request/external-demand run time |
| `pump_post_run_seconds` | 120 | Direct pump post-run |
| `minimum_off_time_seconds` | 180 | Minimum request-off interval before restart |
| `target_supply_temperature_entity` | `null` | Writable `number` or `input_number` receiving supply target |
| `heating_supply_target` | 32 | Constant heating target and weather-compensation fallback |
| `cooling_supply_target` | 18 | Constant cooling target |
| `packing_mode` | `simultaneous` | `simultaneous` or `staggered` slots |
| `t_cycle_seconds` | 720 | Initial cycle length |
| `t_cycle_min` / `t_cycle_max` | 360 / 1440 | Dynamic cycle bounds |
| `rh_alert` / `rh_fault` | 60 / 70 | Cooling humidity thresholds, % |
| `dp_safety_margin_c` | 2 | Cooling dew-point margin |
| `instance_temperature_fallback` | `false` | Limited heating with entry-median room temperature |
| `heating_control_strategy` | `legacy` | `legacy`, `observe`, or `adaptive` |
| `thermal_parameters` | Profile defaults | Advanced thermal parameter object |
| `supply_control` | Constant strategies | Supply policy object described below |

External control requires a demand entity and cleared direct pump/source/changeover
fields. Demand and reported circuit state are valid only in external control.
External timing values are nonnegative whole seconds; UI fields allow 0–3600.

## Zone fields

| Key | Default | Meaning |
| --- | --- | --- |
| `id`, `name` | Required | Unique identifier and display name |
| `sensor_air`, `sensor_rh`, `switch_actuator` | Required | Room sensors and actuator |
| `support_mode` | `BOTH` | `HEAT`, `COOL`, or `BOTH` |
| `sensor_floor`, `window_switch` | Unconfigured | Optional floor sensor/contact; clear with `null` |
| `floor_limits` | `null` | `heat_min`, `heat_max`, `cool_min`, `cool_max`; requires a valid floor sensor |
| `temperature_filter_enabled` | `true` | 180-second room EMA |
| `open_s`, `close_s` | 60 / 60 | Actuator opening/closing time |
| `zone_min_on_s`, `zone_min_off_s` | 180 / 180 | Minimum zone activation/rest time |
| `thermal_profile` | `underfloor` | `underfloor` or `radiator` |
| `thermal_parameters` | Entry/profile settings | Zone overrides of thermal parameters |

`heat_max` and `cool_min` enforce heating/cooling blocks respectively.
`heat_min` and `cool_max` contribute floor diagnostics only; they do not force
actuator demand. Floor settings never replace room setpoints.

## Supply policy

All keys in this section belong inside `global.supply_control`. The UI separates
curve and tuning objects, but the exported policy uses these flat keys.

| Key | Default | Meaning |
| --- | --- | --- |
| `heating_strategy` / `cooling_strategy` | `constant` / `constant` | Heating also accepts `weather_compensated` |
| `outdoor_sensor`, `supply_sensor`, `return_sensor` | `null` | Sensor entities; outdoor required for weather compensation |
| `outdoor_min` / `outdoor_max` | −15 / 15 | Outdoor interval |
| `supply_points` | `[40, 36, 32, 28, 24]` | 2–50 evenly spaced points; nonincreasing with warmer outdoor temperature |
| `heating_min` / `heating_max` | 20 / 45 | Heating supply limits |
| `cooling_min` / `cooling_max` | 5 / 30 | Cooling supply limits |
| `learning_mode` | `off` | `off`, `learn`, or `frozen` |
| `boost_enabled` | `true` | Independent recovery boost for weather compensation |
| `sample_seconds` | 60 | Observation interval; effectively at least 60 in the integration |
| `max_gap_seconds` | 120 | Gap that invalidates observations/trials |
| `sensor_max_age_seconds` | 0 | Report-age limit; 0 disables it |
| `trend_seconds` | 3600 | Trend window, requiring at least 90% temporal coverage |
| `minimum_active_fraction` | 0.2 | Minimum reported activation fraction |
| `learning_seconds` / `probe_seconds` | 86400 / 86400 | Accumulated valid time before/during a trial |
| `learning_step` | 0.5 | Maximum trial step, °C |
| `correction_limit` | 5 | Maximum absolute learned point correction, °C |
| `comfort_tolerance` | 0.3 | Comfort-deficit tolerance, °C |
| `comfort_persistence_seconds` | 1800 | Persistent degradation before early rejection |
| `minimum_learning_improvement` | 0.05 | Minimum mean improvement for an upward trial, °C |
| `probe_outdoor_tolerance` | 2 | Outdoor change interrupting a trial, °C |
| `boost_deficit` | 1 | Deficit threshold for recovery boost, °C |
| `boost_gain` | 2 | Boost per degree of deficit, moderated by recovery |
| `boost_max` | 5 | Maximum boost, °C, within final supply limits |
| `boost_rate_per_hour` | 1 | Maximum boost change, °C/hour |
| `minimum_recovery_rate` | 0.1 | Reference room recovery, °C/hour |
| `fault_seconds` | 21600 | Persistent insufficient-response window |
| `recovery_seconds` | 7200 | Acceptable-response period for recovery |
| `supply_tolerance` | 5 | Persistent mean supply-target deviation, °C |
| `delta_t_alert` | 15 | Persistent mean supply-return difference, °C |
| `write_interval_seconds` | 60 | Minimum operational write/retry interval |
| `write_delta` | 0.2 | Minimum target change for a normal write, °C |
| `write_refresh_seconds` | 900 | Periodic unchanged-target refresh |

Windows and maximum gaps cover at least two effective sample intervals.
Defaults are starting values for calibration; see [Supply control](../features/supply-control.md).
For compatibility, runtime entries without a `supply_control` block retain
0–90°C supply limits rather than the explicit policy defaults above.

## Thermal parameters

`global.thermal_parameters` provides entry overrides;
`zones[].thermal_parameters` provides zone overrides. Units are minutes except
where indicated. These values are model assumptions, not measured equipment data.

| Parameter | Underfloor | Radiator | Bounds |
| --- | --- | --- | --- |
| `delay_minutes` | 45 | 20 | 1–120 |
| `persistence_minutes` | 180 | 45 | 5–360 |
| `trend_minutes` | 60 | 30 | 5–180 |
| `horizon_minutes` | 360 | 180 | 30–720 |
| `integral_minutes` | 360 | 180 | 30–1440 |
| `gain_per_hour` | 0.6 | 0.6 | 0.001–10 °C/hour |
| `loss_per_hour` | 0.15 | 0.15 | 0–5 °C/hour |
| `comfort_below` / `comfort_above` | 0.2 / 0.3 | 0.2 / 0.3 | 0–2°C |
| `deficit_weight` | 2 | 2 | 1–10 |
| `variation_cost` / `start_cost` | 0.02 / 0.01 | 0.02 / 0.01 | 0–10 |
| `supply_reference` | `null` | `null` | 5–90°C or `null` |

See [Adaptive heating](../features/adaptive-control.md) for eligibility and comfort limitations.

## Actions

The integration registers these actions:

| Action | Fields and effect |
| --- | --- |
| `virtual_climate.update_zone` | Required `zone_id`; optional `floor_limits`, `temperature_filter_enabled`, `open_s`, `close_s`, `zone_min_on_s`, `zone_min_off_s`, `sensor_floor`, `window_switch`, `support_mode`. Saves options and reloads the matching entry. |
| `virtual_climate.reset_supply_learning` | Required `entry_id`; resets supply corrections/experience while preserving the base curve. |

`update_zone` requires a zone ID identifying exactly one configured entry;
ambiguous IDs across entries are rejected. Saving zone options can interrupt
operation through entry reload, as described in [Configuration](../configuration.md#saving-and-reload).
