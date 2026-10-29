import unittest
from copy import deepcopy
from types import SimpleNamespace

from support import options_flow


class OptionalEntityTests(unittest.IsolatedAsyncioTestCase):
    async def test_temperature_filter_defaults_and_toggle_survive_edit_export_import(self):
        ns = options_flow()
        zone = dict(id='room', name='Room', sensor_air='sensor.air', sensor_rh='sensor.rh',
                    switch_actuator='switch.room')
        self.assertTrue(ns['_coerce_zone_defaults'](dict(zone))['temperature_filter_enabled'])
        entry = SimpleNamespace(data={'zones': [zone]}, options={})
        flow = ns['VirtualClimateOptionsFlow'](entry)
        flow.selected_zone_id = 'room'
        form = await flow.async_step_zone_edit()
        payload = {k: v for k, v in zone.items() if k not in ('id', 'name')}
        payload['temperature_filter_enabled'] = False
        result = await flow.async_step_zone_edit(form['data_schema'](payload))
        entry.options = result['data']
        merged = ns['get_current_config'](entry)
        exported = ns['_build_export_payload'](merged)
        _, imported = ns['_parse_import_payload_value'](exported)
        self.assertFalse(imported[0]['temperature_filter_enabled'])
        reopened = ns['VirtualClimateOptionsFlow'](entry)
        self.assertFalse(reopened.current_config['zones'][0]['temperature_filter_enabled'])
        with self.assertRaises(ValueError):
            ns['_coerce_zone_defaults'](dict(zone, temperature_filter_enabled='false'))

    async def test_clear_retain_replace_survive_saved_options_and_reload(self):
        ns = options_flow()
        original = {
            'id': 'noah', 'name': 'Noah', 'sensor_air': 'sensor.air', 'sensor_rh': 'sensor.rh',
            'switch_actuator': 'switch.noah', 'sensor_floor': 'sensor.old_floor',
            'window_switch': 'binary_sensor.old_window',
        }
        for field in ('sensor_floor', 'window_switch'):
            for submitted in (None, original[field], 'sensor.new' if field == 'sensor_floor' else 'binary_sensor.new'):
                with self.subTest(field=field, submitted=submitted):
                    entry = SimpleNamespace(data={'zones': [deepcopy(original)]}, options={})
                    flow = ns['VirtualClimateOptionsFlow'](entry)
                    flow.selected_zone_id = 'noah'
                    form = await flow.async_step_zone_edit()
                    payload = {key: value for key, value in original.items() if key not in ('id', 'name', field)}
                    if submitted is not None:
                        payload[field] = submitted
                    result = await flow.async_step_zone_edit(form['data_schema'](payload))
                    entry.options = result['data']
                    merged = ns['get_current_config'](entry)['zones'][0]
                    self.assertEqual(merged[field], submitted)
                    reopened = ns['VirtualClimateOptionsFlow'](entry)
                    self.assertEqual(reopened.current_config['zones'][0][field], submitted)


if __name__ == '__main__':
    unittest.main()
