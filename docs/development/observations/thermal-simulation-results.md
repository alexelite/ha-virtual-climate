# Thermal simulation results

Generated on 2026-11-06 (UTC). Source fingerprints identify the tested revision, including uncommitted changes.

| Source | SHA-256 |
| --- | --- |
| `custom_components/virtual_climate/thermal_control.py` | `05c24daffdd684f6eb111ed1e6814997aaedde133aca98d0a65ecf7a341f56f4` |
| `simulations/thermal_acceptance.py` | `3e566813b7f2877ca705464d091acdf9862e861f5f634974c0a89f475f681aff` |

## Method and scope

Synthetic plant: gain 0.6°C/hour, loss 0.45°C/hour (0.15 at low load), minimum pulse 9 minutes, minimum pause 4 minutes, and a fixed 12-minute legacy cycle. Four days of control are simulated per scenario. Delays range from 20 to 60 minutes and persistence from 45 to 180 minutes. These assumptions strongly influence the comparison.

Weighted deficit is twice the integrated squared deviation below setpoint−0.2°C. Severe overshoot integrates squared deviation above setpoint+0.6°C, in °C²·hour. The severity threshold is a simulation convention. Starts are actuator transitions, not confirmed combustion.

The after-learning stage includes nine synthetic training days and rebuilds active history after restoration. The JSON records model eligibility and actual predictive minutes. An already accurate initial profile may not demonstrate 15% improvement and remains on initial PI.

## Results

**Full comfort acceptance is not met.** Unfavorable results are retained.

| Scenario | Deficit legacy / PI / after learning | Severe overshoot legacy / PI / after learning | Starts legacy / PI / after learning | Initial PI acceptance |
| --- | --- | --- | --- | --- |
| maintenance_delay_30 | 2.331 / 16.530 / 15.698 | 0.000 / 0.000 / 0.000 | 360 / 89 / 93 | fail |
| maintenance_delay_60 | 20.694 / 29.178 / 24.535 | 0.000 / 0.000 / 0.000 | 360 / 80 / 85 | fail |
| maintenance_independent_no_supply | 9.226 / 21.475 / 19.535 | 0.000 / 0.000 / 0.000 | 360 / 84 / 94 | fail |
| maintenance_modulating_oscillating_supply | 70.186 / 23.340 / 21.576 | 0.000 / 0.000 / 0.000 | 356 / 88 / 82 | pass |
| maintenance_radiator | 0.299 / 3.830 / 3.192 | 0.000 / 0.000 / 0.000 | 360 / 104 / 68 | fail |
| low_load_initial_pi | 0.000 / 3.028 / 3.091 | 0.000 / 0.028 / 0.016 | 127 / 92 / 92 | fail |
| recovery | 116.119 / 72.142 / 69.768 | 0.000 / 0.000 / 0.000 | 321 / 81 / 90 | functional scenario |
| setpoint_decrease | 107.757 / 133.164 / 21.689 | 0.000 / 0.796 / 1.422 | 306 / 66 / 83 | functional scenario |
| external_heat | 37.750 / 37.166 / 17.319 | 0.000 / 0.062 / 0.103 | 344 / 83 / 98 | functional scenario |
| sensor_gap_restart_window | 162.865 / 54.785 / 44.431 | 0.000 / 0.000 / 0.000 | 247 / 52 / 57 | functional scenario |

## Interpretation and limitations

Maintenance acceptance requires reduced weighted deficit without increased severe overshoot or starts versus legacy. Reduced starts do not compensate for worse deficit or overshoot. Legacy may achieve near-zero deficit by extending small pulses to the minimum duration. Low load, setpoint changes, and external heat expose additional calibration limitations.

The comparison is between synthetic scheduling policies, not a complete Home Assistant service simulation or a hydraulic model. Deterministic coordinator tests separately cover protections, bounded accounting, persistence, multiple zones, and command identity in observe/legacy. Neither those tests nor these scenarios establish comfort in physical equipment.

The variation/start penalties 0.02/0.01 are explicit assumptions; they are not established calibration for general use. These results do not support recommending adaptive control as a comfort improvement across the maintenance scenarios.

## Reproduce

Run `.venv/bin/python simulations/thermal_acceptance.py` from the repository root. The generator updates this report and [numerical results](thermal-simulation-results.json). See [Testing](../testing.md) and [Adaptive heating](../../features/adaptive-control.md).
