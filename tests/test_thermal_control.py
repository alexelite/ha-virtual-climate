"""Deterministic delayed-plant policy and eligibility tests, no HA dependency."""
import unittest
from math import exp
from support import thermal_module as thermal, coordinator, zone, options_flow


class ThermalPolicyTests(unittest.TestCase):
    def test_delay_and_residual_are_not_instantaneous_heat(self):
        c = thermal.ThermalZone(parameters=dict(delay_minutes=30, persistence_minutes=180))
        for now in range(0, 1800, 60):
            c.update(now, 20, 22, True, 1)
            self.assertEqual(c.effect, 0)
        c.update(1800, 20, 22, False, 1)
        self.assertGreater(c.effect, 0)
        for now in range(1860, 7200, 60):
            c.update(now, 20, 22, False, 1)
        self.assertGreater(c.effect, .02)

    def test_supply_contributes_below_target_and_caps_at_two(self):
        c = thermal.ThermalZone()
        c.update(0, 20, 22, True, 1, supply=30, reference=40)
        self.assertEqual(c.previous_input, .5)
        c.update(60, 20, 22, True, 1, supply=80, reference=40)
        self.assertEqual(c.previous_input, 2)
        c.update(120, 20, 22, True, 1, supply=None, reference=40)
        self.assertEqual(c.previous_input, 1)
        self.assertFalse(c.diagnostics()['supply_weighted'])

    def test_integral_saturates_and_suspends_without_own_temperature(self):
        c = thermal.ThermalZone()
        for now in range(0, 36000, 60):
            c.update(now, 21.7, 22, False, .2)
        self.assertGreater(c.integral, .1)
        saved = c.integral
        c.update(36000, None, 22, False, .2)
        self.assertEqual(c.integral, saved)
        c.update(36060, 20, 22, False, 1, availability=False)
        self.assertEqual(c.integral, saved)
        c.update(36120, 20, 22, False, 1, blocked=True)
        self.assertEqual(c.integral, saved)
        c.update(36180, 22, 20, False, 0)
        self.assertEqual(c.integral, 0)
        self.assertEqual(c.balance, 0)

    def test_low_demand_accumulates_and_real_minimum_holds_are_debited(self):
        c = thermal.ThermalZone()
        for now in range(0, 3000, 60):
            d = c.update(now, 22, 22, False, .1, minimum_pulse=300)
            self.assertFalse(d['pulse_on'])
        d = c.update(3000, 22, 22, False, .1, minimum_pulse=300)
        self.assertTrue(d['pulse_on'])
        c.update(3060, 22, 22, True, .1)
        for now in range(3120, 3661, 60):
            c.update(now, 22, 22, True, .1)
        self.assertLess(c.balance, 0)
        for now in range(3720, 20000, 60):
            c.update(now, 22, 22, False, 1, max_balance=600)
        self.assertLessEqual(c.balance, 600)

    def test_fault_manual_window_gap_and_restart_clear_credit(self):
        c = thermal.ThermalZone()
        for now in range(0, 1000, 60):
            c.update(now, 21, 22, False, .5)
        self.assertGreater(c.balance, 0)
        snapshot = c.snapshot()
        restarted = thermal.ThermalZone()
        restarted.restore(snapshot)
        self.assertEqual(restarted.balance, 0)
        self.assertFalse(restarted.warm)
        c.update(2000, 21, 22, False, .5)
        self.assertEqual(c.balance, 0)
        c.update(2060, 21, 22, False, .5, blocked=True)
        self.assertEqual(c.balance, 0)

    def test_model_needs_seven_valid_days_and_informative_holdout(self):
        c = thermal.ThermalZone('radiator')
        self.assertFalse(c.fit(1e6))
        # Generate a different real plant with informative heat/pause transitions.
        delay, persistence, gain, loss = 30, 67.5, .9, .25
        pending, effect, air = [0.] * delay, 0., 20.
        for minute in range(9 * 1440):
            on = (minute // 180) % 2 == 0
            pending.append(float(on))
            delayed = pending.pop(0)
            effect = effect * exp(-1/persistence) + delayed * (1-exp(-1/persistence))
            air += (gain * effect-loss)/60
            c.update(minute*60, air, air+.1, on, .1)
        self.assertTrue(c.fit(2e6))
        self.assertTrue(c.validated)
        self.assertGreaterEqual(c.validation['improvement'], .15)
        self.assertFalse(c.warm)
        restored = thermal.ThermalZone('radiator')
        restored.restore(c.snapshot())
        self.assertTrue(restored.validated)
        self.assertFalse(restored.warm)

    def test_constant_activity_cannot_identify_gain_and_loss(self):
        c = thermal.ThermalZone()
        for minute in range(8 * 1440):
            c.update(minute*60, 22, 22, False, 0)
        self.assertFalse(c.fit(2e6))
        self.assertFalse(c.validated)

    def test_initial_profile_and_configuration_validation(self):
        self.assertEqual(thermal.ThermalZone().parameters['delay_minutes'],45)
        self.assertEqual(thermal.ThermalZone('radiator').parameters['persistence_minutes'],45)
        for bad in ({'delay_minutes':0},{'gain_per_hour':float('nan')},{'start_cost':-1},{'unknown':1}):
            with self.assertRaises(ValueError):thermal.normalize(bad)

    def test_equal_prediction_cost_keeps_existing_demand(self):
        c = thermal.ThermalZone(parameters=dict(variation_cost=0,start_cost=0))
        c.previous_demand = .35
        c.forecast = lambda *args: ([22]*360,0)
        self.assertEqual(c.choose(22,22,300,1440), .35)


class ThermalIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_observe_has_identical_real_commands_to_legacy(self):
        results=[]
        for strategy in ('legacy','observe'):
            m,h,clock=coordinator(config={'heating_control_strategy':strategy,'zones':[{'id':'zone_1'}]},zones=[zone(delta=.3)])
            try:
                for _ in range(60):
                    await m._on_tick(None)
                    clock.advance(60)
                results.append([(s,e) for _,s,e in h.calls])
                if strategy=='observe':
                    self.assertIn('zone_1',m.thermal.diagnostics)
                    self.assertIn('actual_actuator_on',m.thermal.diagnostics['zone_1'])
            finally:
                for task in h.tasks:task.cancel()
        self.assertEqual(*results)

    async def test_adaptive_accumulates_small_pulses_and_hard_blocks_win(self):
        m,h,clock=coordinator(config={'heating_control_strategy':'adaptive','zones':[{'id':'zone_1'}]},zones=[zone(delta=.15)])
        for _ in range(10):
            await m._on_tick(None)
            clock.advance(60)
        self.assertEqual(h.states.get('switch.zone_1').state,'off')
        for _ in range(50):
            await m._on_tick(None)
            clock.advance(60)
        self.assertTrue(any(s=='turn_on' for _,s,_ in h.calls))
        m._zones['zone_1']['eligible_window']=False
        await m._on_tick(None)
        self.assertEqual(m.thermal.zones['zone_1'].balance,0)
        self.assertEqual(h.states.get('switch.zone_1').state,'off')
        for task in h.tasks:task.cancel()

    async def test_thermal_options_and_profiles_roundtrip(self):
        from types import SimpleNamespace
        ns=options_flow()
        entry=SimpleNamespace(data={'global_co_mode_entity':'select.mode','zones':[dict(id='room',name='Room',sensor_air='sensor.room',sensor_rh='sensor.rh',switch_actuator='switch.room',thermal_profile='radiator')]},options={})
        flow=ns['VirtualClimateOptionsFlow'](entry)
        result=await flow.async_step_thermal_control({'heating_control_strategy':'observe','thermal_parameters':{'start_cost':.03}})
        entry.options=result['data']
        current=ns['get_current_config'](entry)
        exported=ns['_build_export_payload'](current)
        global_config,zones=ns['_parse_import_payload_value'](exported)
        self.assertEqual(global_config['heating_control_strategy'],'observe')
        self.assertEqual(zones[0]['thermal_profile'],'radiator')
        self.assertEqual(ns['_normalize_global_config']({'global_co_mode_entity':'select.mode'})['heating_control_strategy'],'legacy')

class ThermalRegressionTests(unittest.IsolatedAsyncioTestCase):
    async def test_cooling_commands_are_unchanged_for_all_strategies(self):
        commands=[]
        for strategy in ('legacy','observe','adaptive'):
            m,h,clock=coordinator(config={'test_mode':'COOL','heating_control_strategy':strategy,
                                        'zones':[{'id':'zone_1'}]},zones=[zone(delta=-.6)])
            for _ in range(20):
                await m._on_tick(None)
                clock.advance(60)
            commands.append([(s,e) for _,s,e in h.calls])
            for task in h.tasks: task.cancel()
        self.assertEqual(commands[0],commands[1])
        self.assertEqual(commands[0],commands[2])

    async def test_minimum_source_and_postrun_are_evaluated_before_start(self):
        m,h,clock=coordinator(config={'heating_control_strategy':'adaptive','zones':[{'id':'zone_1'}],
            'heating_source_entity':'switch.boiler','minimum_run_time_seconds':1800,
            'pump_post_run_seconds':120,'t_cycle_max':1440},zones=[zone(delta=1.5)])
        h.states.set('switch.boiler','off')
        for _ in range(120):
            await m._on_tick(None)
            clock.advance(60)
        self.assertEqual(h.states.get('switch.zone_1').state,'off')
        self.assertEqual(h.states.get('switch.boiler').state,'off')
        self.assertEqual(m.thermal.diagnostics['zone_1']['reason'],'minimum_pulse_exceeds_cycle_limit')
        self.assertLessEqual(m.thermal.zones['zone_1'].balance,1440)
        for task in h.tasks:task.cancel()

    async def test_multiple_zones_keep_separate_credit_and_protection(self):
        m,h,clock=coordinator(config={'heating_control_strategy':'adaptive',
              'zones':[{'id':'cold'},{'id':'warm'}]},zones=[zone('cold',delta=1.5),zone('warm',delta=0)])
        for _ in range(15):
            await m._on_tick(None)
            clock.advance(60)
        self.assertGreater(m.thermal.zones['cold'].balance,0)
        self.assertEqual(m.thermal.zones['warm'].balance,0)
        m._zones['cold']['limits']['floor']={'heat_max':28}
        m._zones['cold']['t_floor']=29
        await m._on_tick(None)
        self.assertEqual(h.states.get('switch.cold').state,'off')
        self.assertEqual(m.thermal.zones['cold'].balance,0)
        for task in h.tasks:task.cancel()

    async def test_manual_and_suspected_fault_observations_do_not_teach_model(self):
        c=thermal.ThermalZone()
        for minute in range(100):
            c.update(minute*60,20,22,bool(minute%2),.5,learn=False)
        self.assertEqual(c.valid_seconds,0)
        self.assertEqual(len(c.samples),0)
        self.assertGreater(c.effect,0)  # Actual activation still feeds physical memory.

    async def test_persistence_is_separate_and_configuration_changes_reset_experience(self):
        m,h,clock=coordinator(config={'heating_control_strategy':'observe','zones':[{'id':'zone_1'}]})
        await m.thermal.async_start(m._options)
        model=m.thermal.zones['zone_1']
        model.valid_seconds=12345
        model.balance=500
        await m.thermal.async_save(force=True)
        self.assertIn('virtual_climate.test.thermal_zones',h.storage)
        saved=h.storage['virtual_climate.test.thermal_zones']['zone_1']['model']
        self.assertNotIn('balance',saved)
        m.thermal.zones={}
        m.thermal.fingerprints={}
        await m.thermal.async_start(m._options)
        self.assertEqual(m.thermal.zones['zone_1'].valid_seconds,12345)
        self.assertEqual(m.thermal.zones['zone_1'].balance,0)
        m._options['zones'][0]['thermal_profile']='radiator'
        m.thermal.configure(m._options)
        self.assertEqual(m.thermal.zones['zone_1'].valid_seconds,0)
