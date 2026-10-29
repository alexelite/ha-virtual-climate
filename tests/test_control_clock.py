"""Exercise the real climate → coordinator → supply path and scheduled callbacks."""
import asyncio
from copy import deepcopy
import math
import unittest

from support import coordinator, thermostat


class ControlClockTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.instances = []

    async def make(self, temperature='21.07', **options):
        config = dict(id='noah', name='Noah', sensor_air='sensor.air', sensor_rh='sensor.rh',
                      switch_actuator='switch.noah', support_mode='BOTH', sensor_floor=None,
                      open_s=60, close_s=60, zone_min_on_s=180, zone_min_off_s=180)
        m, h, c = coordinator(dict(zones=[config], **options))
        h.states.set('sensor.air', temperature)
        h.states.set('sensor.rh', '50')
        climate = thermostat(h, m.entry, config, manager=m)
        writes = []
        climate.async_write_ha_state = lambda: writes.append((c.now, deepcopy(climate.extra_state_attributes)))
        samples = []
        refresh = climate._async_publish_status

        async def observed_refresh(*args, **kwargs):
            samples.append(c.now)
            await refresh(*args, **kwargs)

        climate._async_publish_status = observed_refresh
        plans = []
        plan = m._plan_cycle

        def observed_plan():
            plans.append(c.now)
            return plan()

        m._plan_cycle = observed_plan
        await climate.async_added_to_hass()
        self.instances.append((m, h, c, climate))
        await m.async_start()
        await self.drain()
        return m, h, c, climate, writes, samples, plans

    async def drain(self):
        for _ in range(12):
            await asyncio.sleep(0)

    async def advance(self, h, c, seconds, before=None):
        for second in range(1, seconds + 1):
            c.advance(1)
            if before:
                before(second)
            await h.dispatch_due()
            await self.drain()

    async def asyncTearDown(self):
        for m, h, c, climate in self.instances:
            await m.async_stop()
            await climate.async_will_remove_from_hass()
        tasks = [task for _, h, _, _ in self.instances for task in h.tasks]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def test_many_sensor_messages_do_not_trigger_extra_samples_or_plans(self):
        m, h, c, climate, writes, samples, plans = await self.make()
        await self.advance(h, c, 59, lambda n: h.states.set('sensor.air', str(21.07 + n / 1000)))
        self.assertEqual(len(samples), 1)
        self.assertEqual(len(plans), 1)
        await self.advance(h, c, 1)
        self.assertEqual(len(samples), 2)
        self.assertEqual(len(plans), 2)
        self.assertAlmostEqual(climate.current_temperature, 21.07 + (1 - math.exp(-1/3)) * .059)
        self.assertTrue(all(name not in ('virtual_climate/zone_status', 'virtual_climate/zone_schedule')
                            for name, _ in h.events))

    async def test_exact_slot_end_does_not_wait_for_next_minute_or_resample(self):
        m, h, c, climate, writes, samples, plans = await self.make()
        end = m._cycle_start + m._slots['noah']['t_on']
        self.assertAlmostEqual(end - c.now, 372)
        await self.advance(h, c, 371)
        self.assertEqual(h.states.get('switch.noah').state, 'on')
        before = (len(samples), len(plans))
        await self.advance(h, c, 1)
        self.assertEqual(h.states.get('switch.noah').state, 'off')
        self.assertEqual((len(samples), len(plans)), before)
        self.assertEqual(h.calls[-1][0], end)

    async def test_source_delays_execute_between_thermal_evaluations(self):
        m, h, c, climate, writes, samples, plans = await self.make(
            heating_source_entity='switch.source', minimum_off_time_seconds=0,
            heating_source_start_delay_seconds=73)
        await self.advance(h, c, 72)
        self.assertFalse(h.states.get('switch.source') and h.states.get('switch.source').state == 'on')
        await self.advance(h, c, 1)
        self.assertEqual(h.states.get('switch.source').state, 'on')
        self.assertEqual(len(samples), 2)
        self.assertEqual(len(plans), 2)

    async def test_loss_and_recovery_reset_filter_on_control_clock(self):
        m, h, c, climate, writes, samples, plans = await self.make()
        h.states.set('sensor.air', 'unavailable')
        await self.advance(h, c, 60)
        self.assertIsNone(climate.current_temperature)
        self.assertEqual(h.states.get('switch.noah').state, 'off')
        h.states.set('sensor.air', '23')
        await self.advance(h, c, 60)
        self.assertEqual(climate.current_temperature, 23)

    async def test_enable_disable_uses_same_input_for_display_demand_and_supply(self):
        m, h, c, climate, writes, samples, plans = await self.make(temperature='20')
        h.states.set('sensor.air', '21')
        await self.advance(h, c, 60)
        expected = 20 + 1 - math.exp(-1/3)
        self.assertAlmostEqual(climate.current_temperature, expected)
        self.assertAlmostEqual(m._zones['noah']['delta_air'], 22 - expected)
        self.assertAlmostEqual(m.supply.controller._history['noah'][-1][1], expected)
        self.assertAlmostEqual(writes[-1][1]['t_air'], expected)
        # Options normally reload the entry. A hot change must also reset memory.
        m.entry.config['zones'][0]['temperature_filter_enabled'] = False
        await self.advance(h, c, 60)
        self.assertEqual(climate.current_temperature, 21)
        self.assertEqual(m.supply.controller._history['noah'][-1][1], 21)
        m.entry.config['zones'][0]['temperature_filter_enabled'] = True
        h.states.set('sensor.air', '21.5')
        await self.advance(h, c, 60)
        self.assertEqual(climate.current_temperature, 21.5)

    async def test_sensor_reporting_each_minute_and_each_five_seconds_have_same_filter(self):
        results = []
        for cadence in (5, 60):
            m, h, c, climate, writes, samples, plans = await self.make(temperature='20')

            def report(second):
                if second % cadence == 0:
                    h.states.set('sensor.air', '21')

            await self.advance(h, c, 180, report)
            self.assertEqual(len(samples), 4)
            results.append(climate.current_temperature)
        self.assertAlmostEqual(results[0], results[1])
        self.assertAlmostEqual(results[0], 20 + 1 - math.exp(-1))

    async def test_shutdown_removes_callbacks_and_cannot_restart(self):
        m, h, c, climate, writes, samples, plans = await self.make()
        await m.async_stop()
        before = len(samples)
        await self.advance(h, c, 700)
        self.assertEqual(len(samples), before)
        self.assertEqual(h.states.get('switch.noah').state, 'off')
        self.assertFalse(h.states.listeners)

    async def test_unchanged_operational_evaluations_do_not_republish_diagnostics(self):
        m, h, c, climate, writes, samples, plans = await self.make()
        notifications = []
        m.async_add_listener(lambda: notifications.append(True))
        before = len(writes)
        for _ in range(10):
            await m._on_tick(None)
        self.assertEqual(len(samples), 1)
        self.assertEqual(len(plans), 1)
        self.assertEqual(len(writes), before)
        self.assertEqual(notifications, [])

    async def test_coincident_deadline_and_periodic_callback_sample_only_once(self):
        m, h, c, climate, writes, samples, plans = await self.make()
        c.advance(60)
        await m._on_tick(None)
        await m._on_thermal_tick(None)
        self.assertEqual(len(samples), 2)
        self.assertEqual(len(plans), 2)

    async def test_periodic_sample_publishes_despite_subsecond_clock_jitter(self):
        m, h, c, climate, writes, samples, plans = await self.make()
        before = len(writes)
        h.states.set('sensor.air', '21.08')
        c.advance(59.98)
        await m._on_thermal_tick(None)
        self.assertEqual(len(writes), before + 1)
        self.assertAlmostEqual(writes[-1][1]['t_air'], climate.current_temperature)

    async def test_explicit_setpoint_replans_without_advancing_temperature_filter(self):
        m, h, c, climate, writes, samples, plans = await self.make()
        initial = climate.current_temperature
        await self.advance(h, c, 5)
        h.states.set('sensor.air', '22')
        await climate.async_set_temperature(temperature=23)
        await self.drain()
        self.assertEqual(climate.current_temperature, initial)
        self.assertEqual(climate.target_temperature, 23)
        self.assertAlmostEqual(m._zones['noah']['delta_air'], 23 - initial)
        self.assertEqual(len(plans), 2)

    async def test_one_hour_of_scheduled_control_respects_source_run_and_flow(self):
        m, h, c, climate, writes, samples, plans = await self.make(
            heating_source_entity='switch.source', circulation_pump_entity='switch.pump',
            minimum_off_time_seconds=180, minimum_run_time_seconds=300,
            pump_post_run_seconds=120)
        source_started = None
        runs = []
        for second in range(1, 3601):
            h.states.set('sensor.air', '23' if second // 600 % 2 else '21.07')
            await self.advance(h, c, 1)
            source = h.states.get('switch.source')
            if source and source.state == 'on':
                if source_started is None:
                    source_started = c.now
                self.assertTrue(m._flow_zones(require_open=True))
            elif source_started is not None:
                runs.append(c.now - source_started)
                source_started = None
        self.assertGreaterEqual(len(runs), 2)
        self.assertTrue(all(length >= 300 for length in runs), runs)
        self.assertEqual(len(samples), 61)
        self.assertLess(len(h.events), 100)
