"""Global sensor attributes and updates through the production coordinator."""
import unittest
from types import SimpleNamespace

from support import callback, coordinator, load_source


def global_sensor(manager, key):
    namespace = dict(
        __name__='test_global_sensor', callback=callback,
        SensorEntity=object,
        VirtualClimateSensorDescription=lambda **kwargs: SimpleNamespace(**kwargs),
        SensorDeviceClass=SimpleNamespace(ENUM='enum', TEMPERATURE='temperature'),
        EntityCategory=SimpleNamespace(DIAGNOSTIC='diagnostic'),
        UnitOfTime=SimpleNamespace(SECONDS='s'),
        UnitOfTemperature=SimpleNamespace(CELSIUS='°C'),
        DeviceInfo=dict,
    )
    load_source('const.py', namespace)
    load_source('sensor.py', namespace, skip_classes=('VirtualClimateSensorDescription',))
    description = next(d for d in namespace['SENSOR_DESCRIPTIONS'] if d.key == key)
    return namespace['VirtualClimateGlobalSensor'](manager.entry, manager, description)


class PlantSensorTests(unittest.IsolatedAsyncioTestCase):
    async def test_direct_profile_exposes_capabilities_without_external_state(self):
        manager, _, _ = coordinator(dict(heating_source_entity='switch.source',
                                          circulation_pump_entity='switch.pump'))
        manager._refresh_global_diagnostics()
        sensor = global_sensor(manager, 'plant_state')

        self.assertEqual(sensor._attr_native_value, 'off')
        attrs = sensor.extra_state_attributes
        self.assertEqual(attrs['circuit_control'], 'direct')
        self.assertEqual(attrs['request_duration_basis'], 'source_request')
        self.assertTrue(attrs['capabilities']['direct_pump'])
        self.assertTrue(attrs['capabilities']['direct_source'])
        self.assertFalse(attrs['capabilities']['external_circuit'])
        self.assertIsNone(attrs['circuit_reported_state'])
        self.assertEqual(attrs['circuit_unavailable_entities'], [])

    async def test_external_feedback_and_availability_publish_without_plant_transition(self):
        manager, hass, _ = coordinator(dict(
            circuit_control='external', circuit_demand_entity='switch.demand',
            circuit_state_entity='sensor.circuit_state',
        ))
        hass.states.set('switch.demand', 'off')
        hass.states.set('sensor.circuit_state', 'off')
        manager._refresh_global_diagnostics()
        sensor = global_sensor(manager, 'plant_state')
        published = []
        sensor.async_write_ha_state = lambda: published.append(
            (sensor._attr_native_value, sensor.extra_state_attributes))
        await sensor.async_added_to_hass()
        self.addAsyncCleanup(sensor.async_will_remove_from_hass)

        attrs = sensor.extra_state_attributes
        self.assertEqual(attrs['circuit_control'], 'external')
        self.assertEqual(attrs['request_duration_basis'], 'demand')
        self.assertTrue(attrs['capabilities']['external_circuit'])
        self.assertTrue(attrs['capabilities']['circuit_state'])
        self.assertFalse(attrs['capabilities']['direct_pump'])
        self.assertFalse(attrs['capabilities']['direct_source'])
        self.assertFalse(attrs['capabilities']['cooling'])

        hass.states.set('sensor.circuit_state', 'postrun')
        manager._refresh_global_diagnostics()
        self.assertEqual(published[-1][0], 'off')
        self.assertEqual(published[-1][1]['circuit_reported_state'], 'postrun')

        hass.states.set('switch.demand', 'unavailable')
        hass.states.set('sensor.circuit_state', 'unavailable')
        manager._refresh_global_diagnostics()
        self.assertEqual(published[-1][0], 'off')
        self.assertCountEqual(published[-1][1]['circuit_unavailable_entities'],
                              ['switch.demand', 'sensor.circuit_state'])

        hass.states.set('switch.demand', 'off')
        hass.states.set('sensor.circuit_state', 'off')
        manager._refresh_global_diagnostics()
        self.assertEqual(published[-1][1]['circuit_unavailable_entities'], [])
        self.assertEqual(published[-1][1]['circuit_reported_state'], 'off')
        self.assertEqual(len(published), 3)

        await sensor.async_will_remove_from_hass()
        hass.states.set('sensor.circuit_state', 'running')
        manager._refresh_global_diagnostics()
        self.assertEqual(len(published), 3)

    async def test_circuit_attributes_do_not_replace_existing_sensor_attributes(self):
        manager, _, _ = coordinator()
        manager._refresh_global_diagnostics()
        running = global_sensor(manager, 'running_zones').extra_state_attributes
        self.assertEqual(running, dict(scheduled_running_zones=0,
                                      actuator_mismatches=0, unavailable_actuators=0))
        learning = global_sensor(manager, 'supply_learning_status').extra_state_attributes
        self.assertIn('supply_command_error', learning)
        self.assertNotIn('circuit_control', learning)
        self.assertIsNone(global_sensor(manager, 'system_mode').extra_state_attributes)
