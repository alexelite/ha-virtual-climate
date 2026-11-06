"""External circuit behavior, exercised through the real coordinator."""
import asyncio
import unittest
from types import SimpleNamespace
from support import coordinator, zone, options_flow


class CircuitTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.instances = []

    def make(self, **overrides):
        config = dict(circuit_control='external', circuit_demand_entity='switch.demand',
                      external_start_delay_seconds=0, external_post_run_seconds=120,
                      minimum_run_time_seconds=0, minimum_off_time_seconds=0,
                      # These direct timings must have no effect on delegated control.
                      pump_start_delay_seconds=400, heating_source_start_delay_seconds=500)
        config.update(overrides)
        m, h, c = coordinator(config, [zone(delta=1.5, actuator=dict(entity_id='switch.zone_1', open_s=0))])
        h.states.set('switch.demand', 'off', c.now - 1000)
        self.instances.append((m, h, c))
        return m, h, c

    async def tick(self, m, h, c, seconds=0):
        c.advance(seconds)
        await h.dispatch_due()
        await m._on_tick(None)
        for _ in range(12):
            await asyncio.sleep(0)
        await m._on_tick(None)
        for _ in range(8):
            await asyncio.sleep(0)

    async def asyncTearDown(self):
        tasks = [task for _, h, _ in self.instances for task in h.tasks]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    async def test_zero_delay_and_no_target_need_no_pump_or_source(self):
        m, h, c = self.make()
        await self.tick(m, h, c)
        self.assertEqual(h.states.get('switch.demand').state, 'on')
        self.assertEqual(m._plant_started_at, c.now)
        self.assertTrue(all(entity in ('switch.zone_1', 'switch.demand') for _, _, entity in h.calls))
        self.assertTrue(m.get_global_diagnostics()['capabilities']['external_circuit'])
        self.assertFalse(m.get_global_diagnostics()['capabilities']['direct_pump'])
        self.assertEqual(m.get_global_diagnostics()['request_duration_basis'], 'demand')

    async def test_zone_opening_and_target_complete_before_demand(self):
        m, h, c = self.make(target_supply_temperature_entity='number.target')
        m._zones['zone_1']['actuator']['open_s'] = 60
        h.states.set('number.target', '32')
        await self.tick(m, h, c)
        self.assertEqual(h.states.get('switch.demand').state, 'off')
        await self.tick(m, h, c, 59)
        self.assertEqual(h.states.get('switch.demand').state, 'off')
        await self.tick(m, h, c, 1)
        self.assertEqual(h.states.get('switch.demand').state, 'on')
        services = [(service, entity) for _, service, entity in h.calls]
        self.assertLess(services.index(('set_value', 'number.target')), services.index(('turn_on', 'switch.demand')))

    async def test_target_failure_blocks_demand_and_unavailable_does_not_change_profile(self):
        m, h, c = self.make(target_supply_temperature_entity='number.target')
        h.states.set('number.target', 'unavailable')
        with self.assertLogs('test_zone_manager', level='ERROR'):
            await self.tick(m, h, c)
        self.assertEqual(h.states.get('switch.demand').state, 'off')
        h.states.set('switch.demand', 'unavailable')
        m._refresh_global_diagnostics()
        diag = m.get_global_diagnostics()
        self.assertEqual(diag['circuit_control'], 'external')
        self.assertIn('switch.demand', diag['circuit_unavailable_entities'])

    async def test_demand_lost_during_delay_never_starts(self):
        m, h, c = self.make(external_start_delay_seconds=30)
        await self.tick(m, h, c)
        m._zones['zone_1']['delta_air'] = 0
        await self.tick(m, h, c, 30)
        self.assertFalse(any(service == 'turn_on' and entity == 'switch.demand' for _, service, entity in h.calls))

    async def test_stop_holds_zones_for_ha_duration_ignoring_reported_off(self):
        m, h, c = self.make(circuit_state_entity='sensor.phase')
        h.states.set('sensor.phase', 'off')
        await self.tick(m, h, c)
        m.entry.config['test_mode'] = 'OFF'
        await self.tick(m, h, c, 1)
        self.assertEqual(h.states.get('switch.demand').state, 'off')
        self.assertEqual(h.states.get('switch.zone_1').state, 'on')
        await self.tick(m, h, c, 119)
        self.assertEqual(h.states.get('switch.zone_1').state, 'on')
        await self.tick(m, h, c, 1)
        self.assertEqual(h.states.get('switch.zone_1').state, 'off')
        self.assertTrue(all(entity in ('switch.zone_1', 'switch.demand') for _, _, entity in h.calls))

    async def test_new_request_cancels_pending_zone_close(self):
        m, h, c = self.make()
        await self.tick(m, h, c)
        m.entry.config['test_mode'] = 'OFF'
        await self.tick(m, h, c, 1)
        m.entry.config['test_mode'] = 'HEAT'
        await self.tick(m, h, c, 30)
        self.assertEqual(h.states.get('switch.demand').state, 'on')
        h.calls.clear()
        await self.tick(m, h, c, 120)
        self.assertEqual(h.states.get('switch.demand').state, 'on')
        self.assertFalse(any(service == 'turn_off' and entity == 'switch.zone_1' for _, service, entity in h.calls))

    async def test_minimum_request_and_pause_use_demand_activation_and_withdrawal(self):
        m, h, c = self.make(minimum_run_time_seconds=60, minimum_off_time_seconds=180)
        await self.tick(m, h, c)
        m.entry.config['test_mode'] = 'OFF'
        await self.tick(m, h, c, 20)
        self.assertEqual(h.states.get('switch.demand').state, 'on')
        await self.tick(m, h, c, 40)
        self.assertEqual(h.states.get('switch.demand').state, 'off')
        m.entry.config['test_mode'] = 'HEAT'
        await self.tick(m, h, c, 30)
        self.assertEqual(h.states.get('switch.zone_1').state, 'on')
        await self.tick(m, h, c, 149)
        self.assertEqual(h.states.get('switch.demand').state, 'off')
        await self.tick(m, h, c, 1)
        self.assertEqual(h.states.get('switch.demand').state, 'on')

    async def test_new_request_during_minimum_run_keeps_demand_on(self):
        m, h, c = self.make(minimum_run_time_seconds=60)
        await self.tick(m, h, c)
        m.entry.config['test_mode'] = 'OFF'
        await self.tick(m, h, c, 20)
        m.entry.config['test_mode'] = 'HEAT'
        h.calls.clear()
        await self.tick(m, h, c, 20)
        await self.tick(m, h, c, 30)
        self.assertEqual(m._plant_state, 'running')
        self.assertFalse(any(service == 'turn_off' and entity == 'switch.demand' for _, service, entity in h.calls))

    async def test_shutdown_waits_for_postrun_before_closing_zones(self):
        m, h, c = self.make()
        await self.tick(m, h, c)
        stop = asyncio.create_task(m.async_stop())
        for _ in range(8):
            await asyncio.sleep(0)
        self.assertEqual(h.states.get('switch.demand').state, 'off')
        self.assertEqual(h.states.get('switch.zone_1').state, 'on')
        self.assertFalse(stop.done())
        c.advance(120)
        await stop
        self.assertEqual(h.states.get('switch.zone_1').state, 'off')

    async def test_external_weather_curve_without_target_does_not_block_local_circuit(self):
        m, h, c = self.make(supply_control=dict(heating_strategy='weather_compensated',
                                               outdoor_sensor='sensor.outdoor'))
        h.states.set('sensor.outdoor', '0')
        await self.tick(m, h, c)
        self.assertEqual(h.states.get('switch.demand').state, 'on')
        self.assertIsNone(m.supply.command_error)
        self.assertTrue(m.get_global_diagnostics()['capabilities']['weather_compensation'])
        self.assertFalse(m.get_global_diagnostics()['capabilities']['supply_target'])

    async def test_fractional_slot_keeps_its_planned_pause(self):
        m, h, c = self.make()
        m._zones['zone_1']['delta_air'] = 0.6
        await self.tick(m, h, c)
        cycle_start = m._cycle_start
        await self.tick(m, h, c, 240)
        self.assertEqual(h.states.get('switch.demand').state, 'off')
        await self.tick(m, h, c, 60)
        self.assertEqual(h.states.get('switch.demand').state, 'off')
        self.assertEqual(m._cycle_start, cycle_start)
        await self.tick(m, h, c, 60)
        self.assertEqual(h.states.get('switch.zone_1').state, 'off')
        await self.tick(m, h, c, 240)
        self.assertEqual(h.states.get('switch.demand').state, 'on')

    async def test_external_cooling_is_disabled(self):
        m, h, c = self.make(test_mode='COOL')
        m._zones['zone_1']['delta_air'] = -1.5
        await self.tick(m, h, c)
        self.assertEqual(h.states.get('switch.zone_1').state, 'off')
        self.assertEqual(h.states.get('switch.demand').state, 'off')

    async def test_import_options_and_export_enforce_single_owner(self):
        ns = options_flow()
        normalize = ns['_normalize_global_config']
        base = dict(global_co_mode_entity='select.mode', circuit_control='external',
                    circuit_demand_entity='switch.demand')
        for key in ('circulation_pump_entity', 'heating_source_entity', 'cooling_source_entity', 'changeover_entity'):
            with self.assertRaises(ValueError):
                normalize(dict(base, **{key: 'switch.conflict'}))
        for config in (dict(base, circuit_demand_entity=None), dict(base, external_post_run_seconds=-1),
                       dict(base, external_start_delay_seconds=float('nan')),
                       dict(base, circuit_control='direct'), dict(base, circuit_demand_entity=42),
                       dict(base, circuit_demand_entity='switch'), dict(base, external_start_delay_seconds='30')):
            with self.assertRaises(ValueError):
                normalize(config)
        flow = ns['VirtualClimateOptionsFlow'](SimpleNamespace(data=base, options={}))
        form = await flow.async_step_global_options()
        saved = await flow.async_step_global_options(form['data_schema'](base))
        self.assertEqual(saved['type'], 'create_entry')
        exported = ns['_build_export_payload'](dict(saved['data'], zones=[dict(id='room', name='Room', sensor_air='sensor.air', sensor_rh='sensor.rh', switch_actuator='switch.room')]))
        global_config, _ = ns['_parse_import_payload_value'](exported)
        self.assertEqual(global_config['circuit_control'], 'external')
        self.assertEqual(global_config['circuit_demand_entity'], 'switch.demand')
        form = await flow.async_step_global_options(dict(base, circulation_pump_entity='switch.conflict'))
        self.assertEqual(form['errors']['base'], 'invalid_circuit')
