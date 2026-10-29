import unittest
import asyncio
from copy import deepcopy
from types import SimpleNamespace

from support import Clock, FakeHass, thermostat


class ClimateDiagnosticsTests(unittest.TestCase):
    def make(self):
        hass = FakeHass(Clock())
        config = {'id': 'noah', 'switch_actuator': 'switch.noah', 'sensor_floor': None, 'support_mode': 'BOTH'}
        entry = SimpleNamespace(config={'zones': [config]})
        entry.entry_id = 'test'
        return thermostat(hass, entry, config), hass

    def test_heat_demand_without_actuator_on_is_idle(self):
        climate, hass = self.make()
        climate._t_air = 20
        hass.states.set('switch.noah', 'off')
        self.assertEqual(climate.hvac_action, 'idle')

    def test_actuator_on_reports_heating_even_during_minimum_run_hold(self):
        climate, hass = self.make()
        climate._t_air = 22.1
        hass.states.set('switch.noah', 'on')
        self.assertEqual(climate.hvac_action, 'heating')

    def test_removed_floor_sensor_has_no_floor_diagnostic(self):
        climate, hass = self.make()
        climate._t_floor = 19.68
        self.assertEqual(climate._floor_limit_state(), 'no_floor_sensor')

    def test_minute_samples_go_directly_to_control_without_bus_events(self):
        climate, hass = self.make()
        climate._z['sensor_air'] = 'sensor.air'
        climate._z['temperature_filter_enabled'] = False
        writes = []
        climate.async_write_ha_state = lambda: writes.append(deepcopy(climate.extra_state_attributes))
        for tick in range(6):
            temperature = 20 + tick * .12
            hass.states.set('sensor.air', str(temperature))
            asyncio.run(climate._async_publish_status(None))
            climate._on_zone_schedule({
                'entry_id': 'test', 'zone_id': 'noah',
                'aggregated_demand_ratio': tick / 100,
            })
            self.assertAlmostEqual(hass.zone_status[-1]['t_air'], temperature)
            hass.clock.advance(60)
        self.assertFalse(climate._attr_should_poll)
        self.assertEqual(hass.events, [])
        self.assertEqual(len(hass.zone_status), 6)
        self.assertEqual(len(writes), 6)
        self.assertEqual(writes[-1]['t_air'], 20.6)

    def test_discrete_changes_publish_inside_the_minute(self):
        climate, hass = self.make()
        writes = []
        climate.async_write_ha_state = lambda: writes.append(climate.hvac_action)
        asyncio.run(climate._async_publish_status(None))
        hass.clock.advance(5)
        hass.states.set('switch.noah', 'on')
        asyncio.run(climate._async_publish_status(None))
        self.assertEqual(writes, ['idle', 'heating'])
        climate._on_zone_schedule({
            'entry_id': 'test', 'zone_id': 'noah', 'blocked_by': 'window_open',
        })
        self.assertEqual(len(writes), 3)

    def test_setpoint_and_manual_off_publish_inside_the_minute(self):
        climate, hass = self.make()
        writes = []
        climate.async_write_ha_state = lambda: writes.append((climate.hvac_mode, climate.target_temperature))
        asyncio.run(climate._async_publish_status(None))
        asyncio.run(climate.async_set_temperature(temperature=23))
        self.assertEqual(writes[-1], ('auto', 23))
        asyncio.run(climate.async_set_hvac_mode('off'))
        self.assertEqual(writes[-1], ('off', 23))

    def test_sensor_loss_and_recovery_bypass_sampling(self):
        climate, hass = self.make()
        writes = []
        climate.async_write_ha_state = lambda: writes.append(climate.current_temperature)
        climate._t_air = 20
        climate._publish_ha_state()
        climate._t_air = None
        climate._publish_ha_state()
        climate._t_air = 20.01
        climate._publish_ha_state()
        self.assertEqual(writes, [20, None, 20.01])

    def test_floor_protection_bypasses_temperature_sampling(self):
        climate, hass = self.make()
        climate._z.update(sensor_floor='sensor.floor', floor_limits={'heat_max': 28})
        writes = []
        climate.async_write_ha_state = lambda: writes.append(climate._floor_limit_state())
        climate._t_floor = 27.9
        climate._publish_ha_state()
        climate._t_floor = 28
        climate._publish_ha_state()
        self.assertEqual(writes, ['ok', 'heat_max_reached'])
