import unittest
from copy import deepcopy
from types import SimpleNamespace

from support import options_flow


class OptionalEntityTests(unittest.IsolatedAsyncioTestCase):
    async def test_supply_targets_move_without_changing_stored_values(self):
        ns = options_flow()
        original = dict(global_co_mode_entity='input_select.mode',
                        target_supply_temperature_entity='number.target',
                        heating_supply_target=37, cooling_supply_target=18)
        entry = SimpleNamespace(data=original, options={})
        flow = ns['VirtualClimateOptionsFlow'](entry)
        form = await flow.async_step_global_options()
        keys = {str(k) for k in form['data_schema'].schema}
        for key in ('heating_supply_target', 'cooling_supply_target', 'target_supply_temperature_entity'):
            self.assertNotIn(key, keys)
        result = await flow.async_step_global_options(form['data_schema']({}))
        entry.options = result['data']
        merged = ns['get_current_config'](entry)
        for key in ('heating_supply_target', 'cooling_supply_target', 'target_supply_temperature_entity'):
            self.assertEqual(merged[key], original[key])
        flow = ns['VirtualClimateOptionsFlow'](entry)
        form = await flow.async_step_supply_control()
        payload = form['data_schema']({'target_supply_temperature_entity': 'number.target'})
        self.assertEqual(payload['heating_supply_target'], 37)
        payload['heating_supply_target'] = 38
        result = await flow.async_step_supply_control(payload)
        entry.options = result['data']
        merged = ns['get_current_config'](entry)
        self.assertEqual(merged['heating_supply_target'], 38)
        exported = ns['_build_export_payload'](merged)
        self.assertEqual(exported['global']['heating_supply_target'], 38)
        flow = ns['VirtualClimateOptionsFlow'](entry)
        form = await flow.async_step_supply_control()
        result = await flow.async_step_supply_control(form['data_schema']({}))
        self.assertIsNone(result['data']['target_supply_temperature_entity'])
        self.assertEqual(result['data']['heating_supply_target'], 38)

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
