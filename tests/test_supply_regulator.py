import asyncio
import unittest
from copy import deepcopy
from datetime import datetime, timezone

from support import coordinator, zone, options_flow, supply_module


class SupplyIntegrationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.instances = []

    def make(self, config=None):
        options = dict(heating_source_entity='switch.source',
                       target_supply_temperature_entity='number.target',
                       minimum_run_time_seconds=0, minimum_off_time_seconds=0,
                       pump_post_run_seconds=0, heating_source_start_delay_seconds=0,
                       cooling_source_start_delay_seconds=0,
                       supply_control=dict(heating_strategy='weather_compensated',
                                           outdoor_sensor='sensor.outdoor', boost_enabled=False))
        options.update(config or {})
        m, h, c = coordinator(options, [zone(delta=1.5, actuator={
            'entity_id': 'switch.noah', 'open_s': 0, 'close_s': 0})])
        h.states.set('number.target', '32')
        h.states.set('sensor.outdoor', '0')
        self.instances.append((m, h, c))
        return m, h, c

    async def tick(self, m, h, c, seconds=0):
        c.advance(seconds)
        await m._on_tick(None)
        for _ in range(24):
            await asyncio.sleep(0)

    async def asyncTearDown(self):
        tasks = [task for _, h, _ in self.instances for task in h.tasks]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    async def test_start_waits_for_accepted_target_and_running_updates_with_weather(self):
        m, h, c = self.make()
        await self.tick(m, h, c)
        self.assertEqual(m._plant_state, 'running')
        calls = h.service_calls
        written = next(i for i, call in enumerate(calls) if call[1] == 'set_value')
        started = next(i for i, call in enumerate(calls) if call[1] == 'turn_on' and call[2]['entity_id'] == 'switch.source')
        self.assertLess(written, started)
        self.assertTrue(calls[written][3]['blocking'])
        h.states.set('sensor.outdoor', '-15')
        await self.tick(m, h, c, 60)
        writes = [data['value'] for domain, service, data, _ in h.service_calls if service == 'set_value']
        self.assertEqual(writes[-1], 40)
        self.assertEqual(m._plant_state, 'running')

    async def test_failed_write_prevents_new_start_and_retries_without_storm(self):
        m, h, c = self.make()
        h.fail_entities.add('number.target')
        await self.tick(m, h, c)
        self.assertFalse(any(service == 'turn_on' and ent == 'switch.source' for _, service, ent in h.calls))
        attempts = sum(service == 'set_value' for _, service, _ in h.calls)
        for _ in range(10):
            await self.tick(m, h, c, 1)
        self.assertEqual(sum(service == 'set_value' for _, service, _ in h.calls), attempts)
        h.fail_entities.clear()
        await self.tick(m, h, c, 60)
        self.assertEqual(m._plant_state, 'running')
        self.assertIsNone(m.supply.command_error)

    async def test_write_failure_during_operation_does_not_stop_source(self):
        m, h, c = self.make()
        await self.tick(m, h, c)
        h.fail_entities.add('number.target')
        h.states.set('sensor.outdoor', '-15')
        await self.tick(m, h, c, 60)
        self.assertEqual(m._plant_state, 'running')
        self.assertEqual(h.states.get('switch.source').state, 'on')
        self.assertEqual(m.supply.command_error, 'target_write_failed')

    async def test_missing_outdoor_writes_constant_fallback_and_cooling_stays_fixed(self):
        m, h, c = self.make()
        await self.tick(m, h, c)
        h.states.set('sensor.outdoor', 'unavailable')
        await self.tick(m, h, c, 60)
        self.assertEqual(m.supply.diagnostics['supply_strategy'], 'fallback_constant')
        self.assertEqual(m.supply.diagnostics['supply_boost'], 0)
        await m.supply.async_update(m.entry.config, 'COOL', m._zones, controlled=True, running=True, force=True)
        self.assertEqual(m.supply.diagnostics['supply_target'], 18)

    async def test_legacy_custom_fixed_targets_survive_without_new_config(self):
        m, h, c = self.make({'supply_control': None, 'heating_supply_target': 60})
        await self.tick(m, h, c)
        self.assertEqual(m.supply.diagnostics['supply_target'], 60)

    async def test_weather_mode_cannot_start_a_source_without_target_output(self):
        m, h, c = self.make({'target_supply_temperature_entity': None})
        with self.assertLogs('test_zone_manager', level='ERROR'):
            await self.tick(m, h, c)
        self.assertFalse(any(service == 'turn_on' and ent == 'switch.source' for _, service, ent in h.calls))
        self.assertEqual(m.supply.command_error, 'target_not_configured')

    async def test_room_monitoring_does_not_require_a_supply_output_or_supply_sensor(self):
        m, h, c = self.make({'target_supply_temperature_entity': None, 'supply_control': {
            'heating_strategy': 'constant', 'trend_seconds': 120, 'fault_seconds': 600,
            'recovery_seconds': 120}})
        m._zones['noah']['delta_air'] = 2
        m._zones['noah']['t_air'] = 20
        await self.tick(m, h, c)
        for _ in range(22):
            await self.tick(m, h, c, 30)
        self.assertIn('zone:noah:insufficient_response', m.supply.diagnostics['supply_faults'])
        self.assertEqual(m._plant_state, 'running')

    async def test_units_device_bounds_nan_and_freshness_are_checked(self):
        m, h, c = self.make()
        outdoor = h.states.get('sensor.outdoor')
        outdoor.state = '32'
        outdoor.attributes['unit_of_measurement'] = '°F'
        await m._update_supply('HEAT', force=True)
        self.assertEqual(m.supply.diagnostics['supply_outdoor'], 0)
        target = h.states.get('number.target')
        target.attributes.update(unit_of_measurement='°F', min=50, max=120)
        self.assertTrue(await m.supply.async_write(m.entry.config, 'HEAT', force=True))
        self.assertEqual([data['value'] for _, service, data, _ in h.service_calls if service == 'set_value'][-1], 89.6)
        target.attributes['max'] = 80
        self.assertFalse(await m.supply.async_write(m.entry.config, 'HEAT', force=True))
        outdoor.state = 'nan'
        await m._update_supply('HEAT', force=True)
        self.assertEqual(m.supply.diagnostics['supply_strategy'], 'fallback_constant')

    async def test_freshness_uses_reports_not_temperature_changes(self):
        m, h, c = self.make()
        m.entry.config['supply_control']['sensor_max_age_seconds'] = 300
        m._options['supply_control']['sensor_max_age_seconds'] = 300
        outdoor = h.states.get('sensor.outdoor')
        outdoor.last_reported = datetime.fromtimestamp(c.now, timezone.utc)
        await m._update_supply('HEAT', force=True)
        self.assertEqual(m.supply.diagnostics['supply_strategy'], 'weather_compensated')
        c.advance(301)
        await m._update_supply('HEAT', force=True)
        self.assertEqual(m.supply.diagnostics['supply_strategy'], 'fallback_constant')
        outdoor.last_reported = datetime.fromtimestamp(c.now, timezone.utc)
        await m._update_supply('HEAT', force=True)
        self.assertEqual(m.supply.diagnostics['supply_strategy'], 'weather_compensated')

    async def test_per_entry_learning_restores_and_manual_reset_preserves_curve(self):
        m, h, c = self.make()
        await m.supply.async_start(m.entry.config)
        m.supply.controller.corrections[2] = .5
        m.supply.controller.experience[2] = 7200
        await m.supply.async_stop()
        replacement = m.supply.__class__(h, 'test')
        await replacement.async_start(m.entry.config)
        self.assertEqual(replacement.controller.corrections[2], .5)
        self.assertEqual(replacement.controller.experience[2], 7200)
        await replacement.async_reset_learning()
        self.assertEqual(replacement.controller.corrections, [0] * 5)
        self.assertEqual(replacement.controller.config['supply_points'], [40, 36, 32, 28, 24])


    async def test_filtered_room_sample_cannot_mask_unavailable_or_old_source(self):
        m, h, c = self.make()
        m.entry.config['zones'] = [dict(id='noah', sensor_air='sensor.air')]
        m._options['zones'] = m.entry.config['zones']
        h.states.set('sensor.air', '21')
        m._zones['noah'].update(t_air=20.5, delta_air=1.5,
                                air_sensor_entity_id='sensor.air', temperature_sampled_at=c.now)
        await m._update_supply('HEAT', force=True)
        self.assertEqual(m.supply.controller._history['noah'][-1][1], 20.5)
        h.states.set('sensor.air', 'unavailable')
        c.advance(60)
        await m._update_supply('HEAT', force=True)
        self.assertNotIn('noah', m.supply.controller._history)
        h.states.set('sensor.air', '21')
        c.advance(61)
        await m._update_supply('HEAT', force=True)
        self.assertNotIn('noah', m.supply.controller._history)

    async def test_legacy_thirty_second_observation_profile_has_effective_minute_cadence(self):
        m, h, c = self.make({'supply_control': {
            'sample_seconds': 30, 'max_gap_seconds': 60, 'trend_seconds': 60,
            'recovery_seconds': 60}})
        config = m.supply._config(m.entry.config)
        self.assertEqual(config['sample_seconds'], 60)
        self.assertEqual(config['max_gap_seconds'], 120)
        self.assertEqual(config['trend_seconds'], 120)
        self.assertEqual(config['recovery_seconds'], 120)
        supply_module.normalize_supply_config(config)


class SupplyConfigTests(unittest.IsolatedAsyncioTestCase):
    async def test_import_export_options_and_clear_sensor(self):
        ns = options_flow()
        payload = {'global': {'global_co_mode_entity': 'input_select.mode', 'supply_control': {
            'heating_strategy': 'weather_compensated', 'outdoor_sensor': 'sensor.outdoor',
            'supply_sensor': 'sensor.supply', 'supply_points': [40, 32, 24]}},
                   'zones': [dict(id='room', name='Room', sensor_air='sensor.air',
                                  sensor_rh='sensor.rh', switch_actuator='switch.room')]}
        globals_, zones = ns['_parse_import_payload_value'](payload)
        from types import SimpleNamespace
        entry = SimpleNamespace(data=dict(globals_, zones=zones), options={})
        flow = ns['VirtualClimateOptionsFlow'](entry)
        form = await flow.async_step_supply_control()
        supplied = form['data_schema']({})
        supplied['outdoor_sensor'] = 'sensor.outdoor'
        result = await flow.async_step_supply_control(supplied)
        entry.options = result['data']
        merged = ns['get_current_config'](entry)
        self.assertIsNone(merged['supply_control']['supply_sensor'])
        exported = ns['_build_export_payload'](merged)
        restored, _ = ns['_parse_import_payload_value'](exported)
        self.assertEqual(restored['supply_control'], merged['supply_control'])

    async def test_weather_without_outdoor_and_unsupported_cooling_are_rejected(self):
        ns = options_flow()
        for value in ({'heating_strategy': 'weather_compensated'},
                      {'cooling_strategy': 'weather_compensated'}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                ns['_normalize_global_config']({'global_co_mode_entity': 'input_select.mode',
                                                'supply_control': value})
