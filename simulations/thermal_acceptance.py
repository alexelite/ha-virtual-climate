"""Reproducible synthetic acceptance cases; no hardware or HA interaction.

Run: .venv/bin/python simulations/thermal_acceptance.py
The initial PI and pulse policy is measured before model eligibility. Model
identification and held-out eligibility are covered separately by unit tests.
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
    lines = [
        '# Raport de simulare termică', '',
        'Sunt păstrate inclusiv rezultatele nefavorabile. Acceptarea completă pentru activare live **nu este îndeplinită**.', '',
        'Instalație sintetică: câștig 0.6°C/h, pierdere 0.45°C/h (0.15°C/h la sarcină mică), impuls minim 9 minute, pauză minimă 4 minute, ciclu legacy fix de 12 minute. Parametrii au un efect puternic asupra comparației; rezultatele nu sunt universale.', '',
        'Deficitul este de două ori integrala pătratului abaterii sub setpoint−0.2°C; depășirea severă integrează pătratul abaterii peste setpoint+0.6°C, în °C²·h. Pragul de severitate este o convenție de simulare. Pornirile sunt tranziții ale actuatorului, fără confirmare de ardere.', '',
        '| Scenariu | Deficit legacy / PI / după învățare | Depășire severă legacy / PI / după învățare | Porniri legacy / PI / după învățare | Acceptare PI |',
        '| --- | --- | --- | --- | --- |',
    ]
    for name, row in results.items():
        metrics = []
        for key in ('weighted_deficit', 'severe_overshoot', 'starts'):
            metrics.append(' / '.join(str(row[stage][key]) if key == 'starts' else f'{row[stage][key]:.3f}'
                                     for stage in ('legacy', 'initial_pi', 'after_learning')))
        accepted = row['maintenance_acceptance']
        status = 'da' if accepted else 'nu' if accepted is False else 'scenariu funcțional'
        lines.append(f'| {name} | {metrics[0]} | {metrics[1]} | {metrics[2]} | {status} |')
    lines += [
        '', 'Etapa de după învățare include nouă zile de observații sintetice și refacerea istoricului după restaurare. Eligibilitatea și minutele predictive efective sunt în JSON. Un profil inițial deja exact nu poate demonstra o îmbunătățire de 15% și rămâne pe PI.', '',
        'Legacy poate avea deficit aproape nul prin prelungirea impulsurilor mici la durata minimă. Reducerea pornirilor nu justifică declararea acceptării când deficitul sau depășirea severă cresc. Cazurile de setpoint și aport extern necesită și ele calibrare.', '',
        'Protecțiile, contabilizarea limitată, persistența și lipsa comenzilor suplimentare în observe sunt verificate separat prin teste deterministe. Criteriile de confort pentru activare live nu sunt încă demonstrate pe toate cazurile. Penalizările 0.02/0.01 sunt explicite, dar nu sunt considerate calibrate pentru activare live.', '',
        'Reproducere: `.venv/bin/python simulations/thermal_acceptance.py`. Datele sunt sintetice și nu reprezintă confort obținut în instalație. Compilarea ESP32 rămâne neverificată; firmware-ul nu a fost instalat.', '',
    ]
    (ROOT/'docs/thermal-simulation-results.md').write_text('\n'.join(lines))


if __name__ == '__main__':
    result=run()
    path=ROOT/'docs/thermal-simulation-results.json'
    path.write_text(json.dumps(result,indent=2)+'\n')
    write_markdown(result)
    print(json.dumps(result,indent=2))
