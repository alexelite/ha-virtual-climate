"""Reproducible synthetic acceptance cases; no hardware or HA interaction.

Run: .venv/bin/python simulations/thermal_acceptance.py
Compares initial PI and a separately trained/restored model against legacy.
Eligibility and actual predictive minutes are reported rather than assumed.
"""
import importlib.util
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('thermal', ROOT/'custom_components/virtual_climate/thermal_control.py')
thermal = importlib.util.module_from_spec(spec)
spec.loader.exec_module(thermal)


def simulate(strategy, scenario):
    profile = scenario.get('profile', 'underfloor')
    model = thermal.ThermalZone(profile)
    delay = scenario.get('delay', 45)
    persistence = scenario.get('persistence', 180)
    loss = scenario.get('loss', .45)
    queue, effect = [0.] * delay, loss/.6
    air = scenario.get('initial', 22.)
    if strategy == 'predictive':
        training = thermal.ThermalZone(profile)
        training_air, training_effect = 22., 0.
        training_queue = [0.] * delay
        for minute in range(9*1440):
            active = (minute//180)%2 == 0
            training_queue.append(float(active))
            delayed = training_queue.pop(0)
            training_effect = training_effect*math.exp(-1/persistence) + delayed*(1-math.exp(-1/persistence))
            training_air += (.6*training_effect-loss)/60
            training.update(minute*60, training_air, training_air+.1, active,.1)
        training.fit(2e6)
        # An already-correct initial profile may not improve by 15%; eligibility
        # remains false and control must stay on the initial PI policy.
        model.restore(training.snapshot())
        # New timeline deliberately has no retained actuator history.
    on, started, stopped, cycle_start, slot = False, -1e9, -1e9, -1e9, 0
    starts = deficit = severe = 0
    maximum = -100.
    min_on = 9  # ceil((60s actuator +30s delay+300s minimum+120s postrun)/60).
    minutes = 4*1440
    predictive_minutes = 0
    for minute in range(minutes):
        target = 22.
        if scenario.get('setpoint') and 1440 <= minute < 2160:
            target = 21.
        if scenario.get('external') and minute % 1440 in range(720, 840):
            external = .25 / 60
        else:
            external = 0
        blocked = scenario.get('block') and minute % 1440 in range(600, 720)
        missing = scenario.get('gap') and minute in range(1440, 1470)
        if scenario.get('restart') and minute == 1440:
            restored = thermal.ThermalZone(profile)
            restored.restore(model.snapshot())
            model = restored
        supply = 40 + (6*math.sin(minute/20) if scenario.get('oscillation') else 0)
        measured_supply = None if scenario.get('no_supply') else supply
        gain = .6 * max(0., min(2., (supply-air)/(40-air)))
        p = max(0., min(1., (target-air)/1.5))
        if strategy in ('adaptive','predictive'):
            result = model.update(minute*60, None if missing else air, target, on, p,
                                  blocked=bool(blocked), supply=measured_supply, reference=40,
                                  minimum_pulse=min_on*60, max_pulse=1440, minimum_off=240,
                                  restart_wait=max(0, 240-(minute-stopped)*60), on_for=(minute-started)*60 if on else 0)
            wanted = result['pulse_on']
            predictive_minutes += model.reason == 'validated_prediction'
        else:
            if minute-cycle_start >= 12:
                cycle_start = minute
                slot = max(min_on, p*12) if p > 0 else 0
            wanted = minute-cycle_start < slot and p > 0
        if blocked or missing:
            wanted = False
        elif on and minute-started < min_on:
            wanted = True
        if wanted and not on and minute-stopped < 4:
            wanted = False
        if on and not wanted:
            stopped = minute
        if wanted and not on:
            starts += 1
            started = minute
        on = wanted
        model.account(minute*60, on, 1440)
        queue.append(float(on))
        delayed = queue.pop(0)
        effect = effect * math.exp(-1/persistence) + delayed * (1-math.exp(-1/persistence))
        air += (gain*effect - loss)/60 + external
        deficit += 2*max(0., target-.2-air)**2/60
        severe += max(0., air-target-.6)**2/60
        maximum = max(maximum, air-target)
        assert abs(model.balance) <= 1440
    return dict(weighted_deficit=round(deficit,5), severe_overshoot=round(severe,5),
                maximum_excess=round(maximum,4), starts=starts, model_eligible=model.validated, predictive_minutes=predictive_minutes)


def run():
    cases = {
        'maintenance_delay_30': {'delay':30},
        'maintenance_delay_60': {'delay':60},
        'maintenance_independent_no_supply': {'no_supply':True},
        'maintenance_modulating_oscillating_supply': {'oscillation':True},
        'maintenance_radiator': {'profile':'radiator','delay':20,'persistence':45},
        'low_load_initial_pi': {'loss':.15},
        'recovery': {'initial':20.},
        'setpoint_decrease': {'setpoint':True},
        'external_heat': {'external':True},
        'sensor_gap_restart_window': {'gap':True,'restart':True,'block':True},
    }
    report = {}
    for name, scenario in cases.items():
        legacy, adaptive, predictive = (simulate(s,scenario) for s in ('legacy','adaptive','predictive'))
        accepted = (adaptive['weighted_deficit'] < legacy['weighted_deficit'] and
                    adaptive['severe_overshoot'] <= legacy['severe_overshoot'] and adaptive['starts'] <= legacy['starts'])
        report[name] = dict(legacy=legacy,initial_pi=adaptive,after_learning=predictive,maintenance_acceptance=accepted if name.startswith('maintenance') or name.startswith('low_load') else None)
    return report


def write_markdown(results):
    """Write generic validation evidence with fingerprints of the tested sources."""
    from datetime import datetime, timezone
    from hashlib import sha256

    fingerprints = {
        str(path.relative_to(ROOT)): sha256(path.read_bytes()).hexdigest()
        for path in (ROOT/'custom_components/virtual_climate/thermal_control.py',
                     Path(__file__).resolve())
    }
    lines = [
        '# Thermal simulation results', '',
        f'Generated on {datetime.now(timezone.utc).date().isoformat()} (UTC). '
        'Source fingerprints identify the tested revision, including uncommitted changes.', '',
        '| Source | SHA-256 |', '| --- | --- |',
        *[f'| `{path}` | `{digest}` |' for path, digest in fingerprints.items()], '',
        '## Method and scope', '',
        'Synthetic plant: gain 0.6°C/hour, loss 0.45°C/hour (0.15 at low load), '
        'minimum pulse 9 minutes, minimum pause 4 minutes, and a fixed 12-minute '
        'legacy cycle. Four days of control are simulated per scenario. '
        'Delays range from 20 to 60 minutes and persistence from 45 to 180 minutes. '
        'These assumptions strongly influence the comparison.', '',
        'Weighted deficit is twice the integrated squared deviation below '
        'setpoint−0.2°C. Severe overshoot integrates squared deviation above '
        'setpoint+0.6°C, in °C²·hour. The severity threshold is a simulation '
        'convention. Starts are actuator transitions, not confirmed combustion.', '',
        'The after-learning stage includes nine synthetic training days and '
        'rebuilds active history after restoration. The JSON records model '
        'eligibility and actual predictive minutes. An already accurate initial '
        'profile may not demonstrate 15% improvement and remains on initial PI.', '',
        '## Results', '',
        '**Full comfort acceptance is not met.** Unfavorable results are retained.', '',
        '| Scenario | Deficit legacy / PI / after learning | Severe overshoot legacy / PI / after learning | Starts legacy / PI / after learning | Initial PI acceptance |',
        '| --- | --- | --- | --- | --- |',
    ]
    for name, row in results.items():
        metrics = []
        for key in ('weighted_deficit', 'severe_overshoot', 'starts'):
            metrics.append(' / '.join(str(row[stage][key]) if key == 'starts' else f'{row[stage][key]:.3f}'
                                     for stage in ('legacy', 'initial_pi', 'after_learning')))
        accepted = row['maintenance_acceptance']
        status = 'pass' if accepted else 'fail' if accepted is False else 'functional scenario'
        lines.append(f'| {name} | {metrics[0]} | {metrics[1]} | {metrics[2]} | {status} |')
    lines += [
        '', '## Interpretation and limitations', '',
        'Maintenance acceptance requires reduced weighted deficit without increased '
        'severe overshoot or starts versus legacy. Reduced starts do not compensate '
        'for worse deficit or overshoot. Legacy may achieve near-zero deficit by '
        'extending small pulses to the minimum duration. Low load, setpoint changes, '
        'and external heat expose additional calibration limitations.', '',
        'The comparison is between synthetic scheduling policies, not a complete '
        'Home Assistant service simulation or a hydraulic model. Deterministic '
        'coordinator tests separately cover protections, bounded accounting, '
        'persistence, multiple zones, and command identity in observe/legacy. '
        'Neither those tests nor these scenarios establish comfort in physical equipment.', '',
        'The variation/start penalties 0.02/0.01 are explicit assumptions; '
        'they are not established calibration for general use. These results '
        'do not support recommending adaptive control as a comfort improvement '
        'across the maintenance scenarios.', '',
        '## Reproduce', '',
        'Run `.venv/bin/python simulations/thermal_acceptance.py` from the repository root. '
        'The generator updates this report and [numerical results](thermal-simulation-results.json). '
        'See [Testing](../testing.md) and [Adaptive heating](../../features/adaptive-control.md).', '',
    ]
    (ROOT/'docs/development/observations/thermal-simulation-results.md').write_text('\n'.join(lines))


if __name__ == '__main__':
    result=run()
    path=ROOT/'docs/development/observations/thermal-simulation-results.json'
    path.write_text(json.dumps(result,indent=2)+'\n')
    write_markdown(result)
    print(json.dumps(result,indent=2))
