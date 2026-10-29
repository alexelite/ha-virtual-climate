import asyncio
import unittest

from support import coordinator, zone


class ZoneManagerTests(unittest.IsolatedAsyncioTestCase):
    async def test_fallback_follows_real_source_and_cannot_keep_it_running(self):
        m, h, c = self.make(config={
            'instance_temperature_fallback': True, 'heating_source_entity': 'switch.boiler',
            'heating_source_start_delay_seconds': 0, 'minimum_off_time_seconds': 0,
            'minimum_run_time_seconds': 0, 'pump_post_run_seconds': 0}, zones=[
                zone('real', delta=0.6, actuator={'entity_id': 'switch.real', 'open_s': 0}),
                zone('missing', t_air=None, delta_air=None, control_setpoint=30)])
        h.states.set('switch.boiler', 'off', c.now - 1000)
        await self.tick(m, h, c)
        await self.tick(m, h, c)
        self.assertEqual(h.states.get('switch.boiler').state, 'on')
        self.assertEqual(h.states.get('switch.missing').state, 'on')
        await self.tick(m, h, c, 240)
        self.assertEqual(h.states.get('switch.boiler').state, 'off')

    async def test_fallback_median_deduplicates_sources_and_rejects_old_samples(self):
        m, h, c = self.make(config={'instance_temperature_fallback': True}, zones=[
            zone('a', t_air=18, delta_air=4, air_sensor_entity_id='sensor.a'),
            zone('duplicate', t_air=18, delta_air=4, air_sensor_entity_id='sensor.a'),
            zone('b', t_air=22, delta_air=0),
            zone('outlier', t_air=35, delta_air=-13),
            zone('old', t_air=10, delta_air=12, temperature_sampled_at=0),
            zone('missing', t_air=None, delta_air=None, control_setpoint=23)])
        await self.tick(m, h, c)
        self.assertEqual(m._zones['missing']['control_temperature'], 22)
        self.assertEqual(m._zones['missing']['fallback_donor_count'], 3)

    async def test_fallback_requires_opt_in_and_never_cools_with_estimates(self):
        for config in ({}, {'instance_temperature_fallback': True, 'test_mode': 'COOL'}):
            m, h, c = self.make(config=config, zones=[zone('real', delta=-1.5),
                zone('missing', t_air=None, delta_air=None, control_setpoint=15)])
            await self.tick(m, h, c)
            self.assertEqual(m._zones['missing']['temperature_source'], 'unavailable')
            self.assertEqual(h.states.get('switch.missing').state, 'off')

    async def test_fallback_keeps_measurement_missing_and_uses_setpoint(self):
        m, h, c = self.make(config={'instance_temperature_fallback': True}, zones=[
            zone('real', delta=1.5),
            zone('missing', t_air=None, delta_air=None, control_setpoint=22)])
        await self.tick(m, h, c)
        z = m._zones['missing']
        self.assertIsNone(z['t_air'])
        self.assertEqual(z['temperature_source'], 'instance_fallback')
        self.assertEqual(z['control_temperature'], 20.5)
        # Followers join only after the plant has actually entered running.
        self.assertEqual(h.states.get('switch.missing').state, 'off')
        m._plant_state = 'running'
        m._plant_mode = 'HEAT'
        await self.tick(m, h, c)
        self.assertEqual(h.states.get('switch.missing').state, 'on')
        z['control_setpoint'] = 19
        m._plan_cycle()
        self.assertEqual(z['requested_p'], 0)
        z.update(t_air=21, delta_air=1)
        m._plan_cycle()
        self.assertEqual(z['temperature_source'], 'measured')

    async def test_fallback_alone_cannot_start_source(self):
        m, h, c = self.make(config={'instance_temperature_fallback': True}, zones=[
            zone('real', delta=0),
            zone('missing', t_air=None, delta_air=None, control_setpoint=30)])
        await self.tick(m, h, c)
        self.assertEqual(m._plant_state, 'off')
        self.assertFalse(m._slots)
        self.assertEqual(h.states.get('switch.missing').state, 'off')

    async def test_fallback_does_not_extend_measured_window(self):
        m, h, c = self.make(config={'instance_temperature_fallback': True}, zones=[
            zone('real', delta=0.6),
            zone('missing', t_air=None, delta_air=None, control_setpoint=30)])
        await self.tick(m, h, c)
        await self.tick(m, h, c, 240)
        self.assertNotEqual(m._plant_state, 'running')
        self.assertEqual(m.get_global_diagnostics()['aggregated_demand_ratio'], 0.4)

    async def test_fallback_disabled_without_donors_or_in_cooling(self):
        for config in ({}, {'instance_temperature_fallback': True},
                       {'instance_temperature_fallback': True, 'test_mode': 'COOL'}):
            m, h, c = self.make(config=config, zones=[
                zone('missing', t_air=None, delta_air=None, control_setpoint=30)])
            await self.tick(m, h, c)
            self.assertFalse(m._slots)
            self.assertEqual(h.states.get('switch.missing').state, 'off')

    async def test_fallback_staggering_does_not_shift_measured_slots(self):
        m, h, c = self.make(config={'instance_temperature_fallback': True, 'packing_mode': 'staggered'}, zones=[
            zone('real', delta=0.6),
            zone('missing', t_air=None, delta_air=None, control_setpoint=30)])
        await self.tick(m, h, c)
        self.assertEqual(m._slots['real']['start_off'], 0)
        self.assertEqual(m._slots['real']['t_on'], 240)

    def setUp(self):
        self.instances = []

    def make(self, config=None, zones=None):
        instance = coordinator(config, zones)
        self.instances.append(instance)
        return instance

    async def tick(self, manager, hass, clock, seconds=0):
        clock.advance(seconds)
        await hass.dispatch_due()
        await manager._on_tick(None)
        for _ in range(8):
            await asyncio.sleep(0)

    async def asyncTearDown(self):
        tasks = [task for _, hass, _ in self.instances for task in hass.tasks]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    async def test_zone_turns_off_at_slot_end(self):
        m, h, c = self.make()
        await self.tick(m, h, c)
        await self.tick(m, h, c, 240)
        self.assertEqual(h.states.get('switch.noah').state, 'off')

    async def test_full_demand_continues_across_cycle_boundary(self):
        m, h, c = self.make(zones=[zone(delta=1.5)])
        await self.tick(m, h, c)
        h.calls.clear()
        await self.tick(m, h, c, 600)
        self.assertEqual(h.calls, [])
        self.assertEqual(h.states.get('switch.noah').state, 'on')

    async def test_cycle_rollover_does_not_publish_zero_or_stop(self):
        m, h, c = self.make(zones=[zone(delta=1.5)])
        await self.tick(m, h, c)
        h.zone_schedules.clear()
        await self.tick(m, h, c, 600)
        schedules = h.zone_schedules
        self.assertTrue(schedules)
        self.assertTrue(all(data['aggregated_demand_ratio'] > 0 for data in schedules))
        self.assertTrue(all(data['coordinator_phase'] != 'stop' for data in schedules))

    async def test_redundant_off_does_not_reset_last_off(self):
        m, h, c = self.make(zones=[zone(delta=0)])
        await self.tick(m, h, c)
        first = dict(m._zone_last_off_at)
        await self.tick(m, h, c, 30)
        self.assertEqual(first, m._zone_last_off_at)

    async def test_demand_remains_positive_during_restart_lockout(self):
        m, h, c = self.make()
        m._zone_last_off_at['noah'] = c.now - 10
        await self.tick(m, h, c)
        self.assertGreater(m.get_global_diagnostics()['aggregated_demand_ratio'], 0)
        self.assertEqual(h.states.get('switch.noah').state, 'off')
        await self.tick(m, h, c, 230)
        self.assertEqual(h.states.get('switch.noah').state, 'on')

    async def test_real_off_requires_full_restart_delay(self):
        m, h, c = self.make(config={'t_cycle_min': 300, 't_cycle_max': 300})
        await self.tick(m, h, c)
        await self.tick(m, h, c, 240)
        self.assertEqual(h.states.get('switch.noah').state, 'off')
        await self.tick(m, h, c, 60)
        self.assertEqual(h.states.get('switch.noah').state, 'off')
        await self.tick(m, h, c, 179)
        self.assertEqual(h.states.get('switch.noah').state, 'off')

    async def test_cycle_length_frozen_while_inputs_change(self):
        m, h, c = self.make(config={'t_cycle_min': 360, 't_cycle_max': 1440})
        await self.tick(m, h, c)
        first = m._cycle_length
        m._zones['noah']['delta_air'] = 1.5
        await self.tick(m, h, c, 1)
        self.assertEqual(m._cycle_length, first)
        await self.tick(m, h, c, first - 1)
        self.assertEqual(m._cycle_length, 1440)

    async def test_staggered_slot_never_shorter_than_minimum_on(self):
        m, h, c = self.make(config={'packing_mode': 'staggered', 't_cycle_min': 300, 't_cycle_max': 300},
                            zones=[zone('a'), zone('b'), zone('c')])
        await self.tick(m, h, c)
        self.assertTrue(all(slot['t_on'] >= 240 for slot in m._slots.values()))
        self.assertTrue(all(slot['start_off'] + slot['t_on'] <= 300 for slot in m._slots.values()))
        self.assertEqual(len(m._slots), 3, 'Staggering must not permanently starve lower-ranked zones')

    async def test_positive_demand_never_rounds_to_zero(self):
        m, h, c = self.make(zones=[zone(delta=0.001)])
        await self.tick(m, h, c)
        self.assertGreater(m.get_global_diagnostics()['aggregated_demand_ratio'], 0)
        m._zones['noah']['delta_air'] = 0
        await self.tick(m, h, c, 1)
        self.assertEqual(m.get_global_diagnostics()['aggregated_demand_ratio'], 0)

    async def test_delayed_confirmation_still_receives_full_minimum_on(self):
        m, h, c = self.make(config={'t_cycle_min': 300, 't_cycle_max': 300})
        h.auto_confirm = False
        await self.tick(m, h, c)
        c.advance(100)
        h.states.set('switch.noah', 'on')
        h.auto_confirm = True
        await self.tick(m, h, c)
        await self.tick(m, h, c, 200)
        self.assertEqual(h.states.get('switch.noah').state, 'on')
        m._zones['noah']['delta_air'] = 0
        await self.tick(m, h, c, 39)
        self.assertEqual(h.states.get('switch.noah').state, 'on')
        await self.tick(m, h, c, 1)
        self.assertEqual(h.states.get('switch.noah').state, 'off')

    async def test_pending_feedback_is_not_counted_as_running(self):
        m, h, c = self.make()
        h.auto_confirm = False
        await self.tick(m, h, c)
        self.assertEqual(m.get_global_diagnostics()['running_zones'], 0)
        data = h.zone_schedules[-1]
        self.assertEqual(data['actuator_state'], 'off')
        self.assertTrue(data['actuator_mismatch'])
        self.assertTrue(data['scheduled_running'])

    async def test_window_interlock_stops_active_zone_immediately(self):
        m, h, c = self.make()
        await self.tick(m, h, c)
        m._zones['noah']['eligible_window'] = False
        await self.tick(m, h, c, 1)
        self.assertEqual(h.states.get('switch.noah').state, 'off')

    async def test_no_demand_honors_zone_minimum_on(self):
        m, h, c = self.make()
        await self.tick(m, h, c)
        m._zones['noah']['delta_air'] = 0
        await self.tick(m, h, c, 1)
        self.assertEqual(h.states.get('switch.noah').state, 'on')
        await self.tick(m, h, c, 239)
        self.assertEqual(h.states.get('switch.noah').state, 'off')

    async def test_global_off_cannot_be_undone_by_stale_callback(self):
        m, h, c = self.make(config={'packing_mode': 'staggered'}, zones=[zone('a'), zone('b')])
        await self.tick(m, h, c)
        m.entry.config['test_mode'] = 'OFF'
        await self.tick(m, h, c, 1)
        await self.tick(m, h, c, 300)
        self.assertTrue(all(h.states.get(f'switch.{zid}').state == 'off' for zid in ('a', 'b')))

    async def test_shutdown_closes_zones_and_cancels_future_actions(self):
        m, h, c = self.make()
        await self.tick(m, h, c)
        await m.async_stop()
        self.assertEqual(h.states.get('switch.noah').state, 'off')
        c.advance(600)
        await h.dispatch_due()
        self.assertEqual(h.states.get('switch.noah').state, 'off')

    async def test_command_failure_does_not_claim_running(self):
        m, h, c = self.make()
        h.fail_entities.add('switch.noah')
        with self.assertLogs(level='ERROR'):
            await self.tick(m, h, c)
        self.assertEqual(m.get_global_diagnostics()['running_zones'], 0)

    async def test_source_waits_for_confirmed_actuator_open_time(self):
        m, h, c = self.make(config={'heating_source_entity': 'switch.source', 'circulation_pump_entity': 'switch.pump'})
        await self.tick(m, h, c)
        self.assertNotIn('on', [s.state for s in [h.states.get('switch.source')] if s])
        await self.tick(m, h, c, 59)
        self.assertIsNone(h.states.get('switch.source'))
        await self.tick(m, h, c, 1)
        self.assertEqual(h.states.get('switch.source').state, 'on')

    async def test_source_never_starts_without_confirmed_open_zone(self):
        m, h, c = self.make(config={'heating_source_entity': 'switch.source'})
        h.auto_confirm = False
        await self.tick(m, h, c)
        await self.tick(m, h, c, 100)
        self.assertFalse(any(service == 'turn_on' and entity == 'switch.source' for _, service, entity in h.calls))

    async def test_source_stays_on_across_full_demand_cycle_rollover(self):
        m, h, c = self.make(config={'heating_source_entity': 'switch.source'}, zones=[zone(delta=1.5)])
        await self.tick(m, h, c)
        await self.tick(m, h, c, 60)
        h.calls.clear()
        await self.tick(m, h, c, 540)
        self.assertEqual(h.calls, [])
        self.assertEqual(m._plant_state, 'running')

    async def test_shutdown_cancels_pending_source_start(self):
        m, h, c = self.make(config={'heating_source_entity': 'switch.source'})
        await self.tick(m, h, c)
        await m.async_stop()
        c.advance(1000)
        for _ in range(8):
            await asyncio.sleep(0)
        self.assertEqual(h.states.get('switch.source').state, 'off')
        self.assertEqual(h.states.get('switch.noah').state, 'off')

    async def test_state_only_diagnostics_preserve_demand(self):
        m, h, c = self.make()
        await self.tick(m, h, c)
        previous = m.get_global_diagnostics()['aggregated_demand_ratio']
        m._publish_zone_diagnostics(None, 'HEAT', 'running')
        self.assertEqual(m.get_global_diagnostics()['aggregated_demand_ratio'], previous)

    async def test_manual_switch_off_is_observed_without_resetting_lockout(self):
        m, h, c = self.make()
        await self.tick(m, h, c)
        c.advance(60)
        h.states.set('switch.noah', 'off')
        await self.tick(m, h, c)
        off_at = m._zone_last_off_at['noah']
        await self.tick(m, h, c, 30)
        self.assertEqual(m._zone_last_off_at['noah'], off_at)
        data = h.zone_schedules[-1]
        self.assertEqual(data['blocked_by'], 'zone_min_off')
        self.assertGreater(data['requested_fraction'], 0)
        self.assertFalse(data['actuator_mismatch'])

    async def test_source_minimum_off_survives_manager_reload(self):
        m, h, c = self.make(config={'heating_source_entity': 'switch.source', 'heating_source_start_delay_seconds': 0})
        h.states.set('switch.source', 'off')
        await self.tick(m, h, c)
        await self.tick(m, h, c, 60)
        self.assertEqual(h.states.get('switch.source').state, 'off')
        await self.tick(m, h, c, 120)
        self.assertEqual(h.states.get('switch.source').state, 'on')

    async def test_startup_cleans_outputs_left_on_with_global_off(self):
        m, h, c = self.make(config={'test_mode': 'OFF', 'heating_source_entity': 'switch.source',
                                    'circulation_pump_entity': 'switch.pump',
                                    'minimum_run_time_seconds': 0, 'pump_post_run_seconds': 0})
        h.states.set('switch.source', 'on')
        h.states.set('switch.pump', 'on')
        h.states.set('switch.noah', 'on')
        await self.tick(m, h, c)
        await self.tick(m, h, c)
        self.assertEqual(h.states.get('switch.source').state, 'off')
        self.assertEqual(h.states.get('switch.pump').state, 'off')
        self.assertEqual(h.states.get('switch.noah').state, 'off')

    async def test_startup_cleans_a_leftover_pump_without_source(self):
        m, h, c = self.make(config={'circulation_pump_entity': 'switch.pump'}, zones=[zone(delta=0)])
        h.states.set('switch.pump', 'on')
        await self.tick(m, h, c)
        self.assertEqual(h.states.get('switch.pump').state, 'off')

    async def test_source_minimum_run_and_pump_postrun(self):
        m, h, c = self.make(config={'heating_source_entity': 'switch.source', 'circulation_pump_entity': 'switch.pump',
                                    'pump_start_delay_seconds': 0, 'heating_source_start_delay_seconds': 0,
                                    'minimum_run_time_seconds': 300, 'pump_post_run_seconds': 120})
        await self.tick(m, h, c)
        await self.tick(m, h, c, 60)
        self.assertEqual(h.states.get('switch.source').state, 'on')
        m._zones['noah']['delta_air'] = 0
        await self.tick(m, h, c, 180)
        self.assertEqual(h.states.get('switch.source').state, 'on')
        await self.tick(m, h, c, 120)
        self.assertEqual(h.states.get('switch.source').state, 'off')
        self.assertEqual(h.states.get('switch.pump').state, 'on')
        self.assertEqual(h.states.get('switch.noah').state, 'on')
        await self.tick(m, h, c, 120)
        await self.tick(m, h, c)
        self.assertEqual(h.states.get('switch.pump').state, 'off')
        self.assertEqual(h.states.get('switch.noah').state, 'off')

    async def prepare_handover(self, delayed=False, cycle=600):
        m, h, c = self.make(config={
            'heating_source_entity': 'switch.source', 'circulation_pump_entity': 'switch.pump',
            'heating_source_start_delay_seconds': 30, 'pump_start_delay_seconds': 0,
            'minimum_off_time_seconds': 180, 'minimum_run_time_seconds': 300,
            'pump_post_run_seconds': 120, 't_cycle_min': cycle, 't_cycle_max': cycle,
        }, zones=[zone('old', delta=0.1), zone('new', delta=0.7)])
        h.states.values.pop('switch.new')
        h.states.set('switch.new', 'off')
        h.states.set('switch.source', 'off')
        original_call = h.services.async_call

        async def call(domain, service, data, **kwargs):
            if delayed and service == 'turn_on' and data.get('entity_id') == 'switch.new':
                h.calls.append((c.now, service, 'switch.new'))
                return
            await original_call(domain, service, data, **kwargs)

        h.services.async_call = call
        await self.tick(m, h, c)
        await self.tick(m, h, c, 180)
        await self.tick(m, h, c, 30)
        self.assertEqual(h.states.get('switch.source').state, 'on')
        return m, h, c

    async def test_handover_keeps_old_path_until_delayed_confirmation_and_open_time(self):
        m, h, c = await self.prepare_handover(delayed=True)
        await self.tick(m, h, c, 30)
        self.assertEqual(h.states.get('switch.source').state, 'on')
        self.assertEqual(h.states.get('switch.old').state, 'on')
        self.assertEqual(h.states.get('switch.new').state, 'off')
        c.advance(2)
        h.states.set('switch.new', 'on')
        await self.tick(m, h, c)
        await self.tick(m, h, c, 59)
        self.assertEqual(h.states.get('switch.old').state, 'on')
        await self.tick(m, h, c, 1)
        self.assertEqual(h.states.get('switch.old').state, 'off')
        self.assertEqual(h.states.get('switch.source').state, 'on')
        self.assertEqual(h.states.get('switch.pump').state, 'on')

    async def test_handover_immediate_feedback_still_waits_for_mechanical_opening(self):
        m, h, c = await self.prepare_handover()
        await self.tick(m, h, c, 30)
        self.assertEqual(h.states.get('switch.new').state, 'on')
        self.assertEqual(h.states.get('switch.old').state, 'on')
        await self.tick(m, h, c, 59)
        self.assertEqual(h.states.get('switch.old').state, 'on')
        await self.tick(m, h, c, 1)
        self.assertEqual(h.states.get('switch.old').state, 'off')
        self.assertEqual(h.states.get('switch.source').state, 'on')

    async def test_cycle_rollover_does_not_close_last_path_before_replacement_opens(self):
        m, h, c = await self.prepare_handover(delayed=True, cycle=240)
        m._zones['old']['delta_air'] = 0
        await self.tick(m, h, c, 30)
        self.assertEqual(h.states.get('switch.old').state, 'on')
        self.assertEqual(h.states.get('switch.source').state, 'on')
        self.assertEqual(m._plant_state, 'running')

    async def test_failed_handover_times_out_with_orderly_stop_and_valid_path(self):
        m, h, c = await self.prepare_handover(delayed=True)
        await self.tick(m, h, c, 30)
        with self.assertLogs(level='WARNING'):
            await self.tick(m, h, c, 91)
        self.assertEqual(m._plant_state, 'stopping')
        self.assertEqual(h.states.get('switch.old').state, 'on')
        await self.tick(m, h, c, 178)
        self.assertEqual(h.states.get('switch.source').state, 'on')
        await self.tick(m, h, c, 1)
        self.assertEqual(h.states.get('switch.source').state, 'off')
        self.assertEqual(h.states.get('switch.pump').state, 'on')
        self.assertEqual(h.states.get('switch.old').state, 'on')
        m._zones['new']['delta_air'] = 0
        await self.tick(m, h, c, 120)
        await self.tick(m, h, c)
        self.assertEqual(h.states.get('switch.pump').state, 'off')
        self.assertEqual(h.states.get('switch.old').state, 'off')

    async def test_handover_cannot_hold_a_safety_blocked_old_path(self):
        m, h, c = await self.prepare_handover(delayed=True)
        await self.tick(m, h, c, 30)
        c.advance(1)
        h.states.set('switch.new', 'on')
        m._zones['old']['eligible_window'] = False
        await self.tick(m, h, c)
        self.assertEqual(h.states.get('switch.old').state, 'off')
        self.assertEqual(h.states.get('switch.source').state, 'off')
        self.assertEqual(h.states.get('switch.pump').state, 'off')

    async def test_handover_stops_if_old_path_is_lost_before_new_path_is_open(self):
        m, h, c = await self.prepare_handover()
        await self.tick(m, h, c, 30)
        c.advance(1)
        h.states.set('switch.old', 'unavailable')
        await self.tick(m, h, c)
        self.assertEqual(h.states.get('switch.new').state, 'on')
        self.assertEqual(h.states.get('switch.source').state, 'off')
        self.assertEqual(h.states.get('switch.pump').state, 'off')

    async def test_two_hour_plant_control_with_delayed_feedback_keeps_source_minimum_run(self):
        m, h, c = self.make(config={
            'heating_source_entity': 'switch.source', 'circulation_pump_entity': 'switch.pump',
            'heating_source_start_delay_seconds': 30, 'pump_start_delay_seconds': 0,
            'minimum_off_time_seconds': 180, 'minimum_run_time_seconds': 300,
            'pump_post_run_seconds': 120, 't_cycle_min': 360, 't_cycle_max': 720,
        }, zones=[zone('a', delta=0.1), zone('b', delta=0.7), zone('c', delta=0.4)])
        h.states.set('switch.source', 'off')
        pending = []
        original_call = h.services.async_call

        async def call(domain, service, data, **kwargs):
            entity = data.get('entity_id')
            if entity in ('switch.a', 'switch.b', 'switch.c'):
                h.calls.append((c.now, service, entity))
                pending.append((c.now + 1, entity, 'on' if service == 'turn_on' else 'off'))
                return
            await original_call(domain, service, data, **kwargs)

        h.services.async_call = call
        values = [0.1, 0.9, 0.3, 0, 1.5, 0.01]
        source_periods = []
        source_started = None
        handover_seen = False
        for second in range(7200):
            c.advance(1)
            for at, entity, state in list(pending):
                if at <= c.now:
                    h.states.set(entity, state)
                    pending.remove((at, entity, state))
            if second % 120 == 0:
                for index, zid in enumerate(('a', 'b', 'c')):
                    m._zones[zid]['delta_air'] = values[(second // 120 + index) % len(values)]
            await self.tick(m, h, c)
            handover_seen |= bool(m._handover_hold_zones)
            if h.states.get('switch.source').state == 'on':
                if source_started is None:
                    source_started = c.now
                self.assertTrue(m._flow_zones(require_open=True), 'Running source lost all open paths')
            elif source_started is not None:
                source_periods.append(c.now - source_started)
                source_started = None
        self.assertTrue(handover_seen, 'Simulation must exercise the repaired path')
        self.assertGreater(len(source_periods), 5, 'Simulation must exercise several complete source sessions')
        self.assertTrue(all(period >= 300 for period in source_periods), source_periods)

    async def test_mode_change_finishes_stop_before_reversing(self):
        m, h, c = self.make(config={'heating_source_entity': 'switch.heat', 'cooling_source_entity': 'switch.cool',
                                    'heating_source_start_delay_seconds': 0, 'cooling_source_start_delay_seconds': 0,
                                    'minimum_run_time_seconds': 0, 'pump_post_run_seconds': 0,
                                    'minimum_off_time_seconds': 0})
        await self.tick(m, h, c)
        await self.tick(m, h, c, 60)
        m.entry.config['test_mode'] = 'COOL'
        m._zones['noah']['co_mode'] = 'COOL'
        m._zones['noah']['delta_air'] = -1
        await self.tick(m, h, c, 1)
        self.assertEqual(h.states.get('switch.heat').state, 'off')
        await self.tick(m, h, c, 1)
        self.assertFalse(h.states.get('switch.cool') and h.states.get('switch.cool').state == 'on')

    async def test_losing_last_path_during_postrun_stops_pump_immediately(self):
        m, h, c = self.make(config={'heating_source_entity': 'switch.source', 'circulation_pump_entity': 'switch.pump',
                                    'heating_source_start_delay_seconds': 0, 'minimum_run_time_seconds': 300})
        await self.tick(m, h, c)
        await self.tick(m, h, c, 60)
        m._zones['noah']['delta_air'] = 0
        await self.tick(m, h, c, 180)
        self.assertEqual(m._plant_state, 'stopping')
        m._zones['noah']['eligible_window'] = False
        await self.tick(m, h, c, 1)
        self.assertEqual(h.states.get('switch.source').state, 'off')
        self.assertEqual(h.states.get('switch.pump').state, 'off')
        self.assertEqual(h.states.get('switch.noah').state, 'off')

    async def test_two_hour_variable_demand_respects_minimum_transitions(self):
        m, h, c = self.make(config={'t_cycle_min': 360, 't_cycle_max': 720}, zones=[zone('a'), zone('b')])
        values = [0.1, 0.9, 0.3, 0, 1.5, 0.01]
        for second in range(7200):
            if second % 120 == 0:
                for index, zid in enumerate(('a', 'b')):
                    m._zones[zid]['delta_air'] = values[(second // 120 + index) % len(values)]
            await self.tick(m, h, c, 1)
        previous = {}
        for at, service, entity in h.calls:
            if entity in previous:
                old_at, old_service = previous[entity]
                self.assertNotEqual(service, old_service)
                self.assertGreaterEqual(at - old_at, 240, (entity, old_service, service, at - old_at))
            previous[entity] = (at, service)


if __name__ == '__main__':
    unittest.main()
