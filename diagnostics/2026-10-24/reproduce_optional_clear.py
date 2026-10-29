"""Reproduce clearing optional entity selectors through schema -> save -> reload.

Requires voluptuous==0.15.2. Example:
  /tmp/ha-virtual-climate-diag-venv/bin/python diagnostics/2026-10-24/reproduce_optional_clear.py

Runs the actual config-flow code with fake HA flow wrappers and selector validators.
Uses real Voluptuous validation. Makes no live HA calls or source changes.
Exit 1 means the current schema restores a cleared optional entity.
"""
import ast
import asyncio
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import voluptuous as vol


ROOT = Path(__file__).resolve().parents[2]


class FakeOptionsFlow:
    def async_show_form(self, **kwargs):
        return dict(type='form', **kwargs)

    def async_create_entry(self, **kwargs):
        return dict(type='create_entry', **kwargs)


namespace = {
    '__name__': 'diagnostic_config_flow',
    'vol': vol,
    'config_entries': SimpleNamespace(OptionsFlow=FakeOptionsFlow),
    'selector': lambda config: lambda value: value,
    'callback': lambda fn: fn,
}
source = ROOT / 'custom_components/virtual_climate/config_flow.py'
tree = ast.parse(source.read_text())
tree.body = [node for node in tree.body
             if not isinstance(node, (ast.Import, ast.ImportFrom))
             and not (isinstance(node, ast.ClassDef) and node.name == 'ConfigFlow')]
tree.body.insert(0, ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0))
ast.fix_missing_locations(tree)
exec(compile(tree, str(source), 'exec'), namespace)

ZONE = {
    'id': 'noah_bedroom', 'name': 'Noah Bedroom',
    'sensor_air': 'sensor.noah_air', 'sensor_rh': 'sensor.noah_rh',
    'switch_actuator': 'switch.ufh_noah_bedroom',
    'sensor_floor': 'sensor.noah_bedrom_th_123_2',
    'window_switch': 'binary_sensor.noah_window',
    'floor_limits': {'heat_min': 23, 'heat_max': 28, 'cool_min': 20, 'cool_max': 24},
    'support_mode': 'BOTH', 'open_s': 60, 'close_s': 60,
    'zone_min_on_s': 180, 'zone_min_off_s': 180,
}


async def round_trip(field, submitted='omit', validate_schema=True):
    entry = SimpleNamespace(data={'zones': [deepcopy(ZONE)]}, options={})
    flow = namespace['VirtualClimateOptionsFlow'](entry)
    flow.selected_zone_id = 'noah_bedroom'
    form = await flow.async_step_zone_edit()
    user_input = {
        'sensor_air': ZONE['sensor_air'],
        'sensor_rh': ZONE['sensor_rh'],
        'switch_actuator': ZONE['switch_actuator'],
    }
    other = 'window_switch' if field == 'sensor_floor' else 'sensor_floor'
    user_input[other] = ZONE[other]
    if submitted != 'omit':
        user_input[field] = submitted
    validated = form['data_schema'](user_input) if validate_schema else user_input
    result = await flow.async_step_zone_edit(validated)
    assert result['type'] == 'create_entry'
    entry.options = result['data']
    restored = namespace['get_current_config'](entry)['zones'][0]
    return validated.get(field), restored[field]


async def main():
    failures = 0
    for field in ('sensor_floor', 'window_switch'):
        validated, restored = await round_trip(field)
        print(f'CURRENT {field}: submitted=<omitted>, after_schema={validated!r}, after_save_and_reload={restored!r}')
        if restored is not None:
            failures += 1
    _, restored = await round_trip('sensor_floor', validate_schema=False)
    assert restored is None, 'Save/merge must preserve explicit clearing when schema is bypassed'
    print('CONTROL: save/merge without schema default injection preserves sensor_floor=None')

    # Probe exactly one variable in memory: suggested display value instead of schema default.
    def suggested_optional_entity(key, domains, default=...):
        description = {} if default in (..., None, '') else {'suggested_value': default}
        return vol.Optional(key, description=description), namespace['selector']({'entity': {'domain': domains}})

    namespace['_optional_entity_field'] = suggested_optional_entity
    for field in ('sensor_floor', 'window_switch'):
        _, restored = await round_trip(field)
        assert restored is None
        _, retained = await round_trip(field, ZONE[field])
        assert retained == ZONE[field]
        _, replaced = await round_trip(field, 'sensor.replacement' if field == 'sensor_floor' else 'binary_sensor.replacement')
        assert replaced.endswith('.replacement')
    print('CANDIDATE: suggested_value preserves clear, retain, and replace for both optional entity fields')
    print(f'{failures} current-schema failures reproduced; this diagnostic run made no source or live HA writes.')
    return bool(failures)


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
