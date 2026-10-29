"""Time-driven policy tests, including interrupted experiments and slow plants."""
import unittest
from copy import deepcopy

from support import supply_module as supply


def config(**overrides):
    result = dict(heating_strategy="weather_compensated", outdoor_sensor="sensor.outdoor",
                  trend_seconds=60, learning_seconds=120, probe_seconds=120,
                  fault_seconds=600, recovery_seconds=60, boost_rate_per_hour=120,
                  comfort_persistence_seconds=30,
                  sample_seconds=30, max_gap_seconds=120)
    result.update(overrides)
    return result


def observation(deficit=0.1, zid="room", on=True, eligible=True):
    return dict(id=zid, air=22 - deficit, deficit=deficit, on=on,
                eligible=eligible, expected=True)


def update(controller, now, deficit=0.1, **kwargs):
    values = dict(mode="HEAT", fixed_target=32, outdoor=0,
                  zones=[observation(deficit)], controlled=True, running=True)
    values.update(kwargs)
    return controller.update(now, **values)


class SupplyPolicyTests(unittest.TestCase):
    def test_curve_points_interpolation_extrapolation_and_final_bounds(self):
        c = supply.SupplyController(config())
        for outdoor, expected in ((0, 32), (-15, 40), (15, 24), (-30, 45), (30, 20), (3.75, 30)):
            with self.subTest(outdoor=outdoor):
                result = update(c, 0, outdoor=outdoor)
                self.assertEqual(result['supply_target'], expected)

    def test_corrections_are_interpolated_not_stepped_at_midpoint(self):
        c = supply.SupplyController(config(learning_mode="frozen"))
        c.corrections[2] = 2
        a = update(c, 0, outdoor=3.74)['supply_learned_correction']
        b = update(c, 30, outdoor=3.76)['supply_learned_correction']
        self.assertAlmostEqual(a, 1, delta=0.01)
        self.assertAlmostEqual(b, 1, delta=0.01)

    def test_cooling_and_constant_mode_do_not_apply_learning_or_boost(self):
        c = supply.SupplyController(config(learning_mode="frozen"))
        c.corrections[2] = 3
        self.assertEqual(update(c, 0, mode="COOL", fixed_target=18)['supply_target'], 18)
        c.configure(dict(c.config, heating_strategy="constant"), 30)
        result = update(c, 60)
        self.assertEqual(result['supply_target'], 32)
        self.assertEqual(result['supply_boost'], 0)

    def test_missing_outdoor_uses_strict_constant_fallback_and_rolls_back_trial(self):
        c = supply.SupplyController(config(learning_mode="learn"))
        for now in range(0, 181, 30):
            update(c, now)
        self.assertIsNotNone(c.probe)
        c.boost = 3
        result = update(c, 210, outdoor=None)
        self.assertEqual((result['supply_target'], result['supply_strategy']), (32, 'fallback_constant'))
        self.assertEqual(result['supply_boost'], 0)
        self.assertIsNone(c.probe)
        self.assertEqual(c.corrections, [0] * 5)

    def test_nearest_point_receives_experience_and_outside_does_not_learn(self):
        c = supply.SupplyController(config(learning_mode="learn", learning_seconds=600))
        for now in range(0, 181, 30):
            update(c, now, outdoor=1)
        self.assertGreater(c.experience[2], 0)
        self.assertEqual(sum(c.experience), c.experience[2])
        before = list(c.experience)
        for now in range(210, 391, 30):
            result = update(c, now, outdoor=-20)
        self.assertEqual(c.experience, before)
        self.assertEqual(result['supply_learning_status'], 'outside_curve_interval')

    def test_boost_uses_worst_eligible_room_not_mean(self):
        c = supply.SupplyController(config())
        rooms = [observation(2, 'cold')] + [observation(0, f'good{i}') for i in range(9)]
        for now in range(0, 181, 30):
            result = update(c, now, zones=rooms)
        self.assertEqual(result['supply_boost'], 4)
        self.assertEqual(result['supply_limiting_zone'], 'cold')
        self.assertEqual(c.corrections, [0] * 5)

    def test_boost_requires_activation_and_accounts_for_recovery_rate(self):
        for on in (False, True):
            c = supply.SupplyController(config())
            for now in range(0, 181, 30):
                deficit = 2 - now / 3600 if on else 2
                result = update(c, now, zones=[observation(deficit, on=on)])
            self.assertEqual(result['supply_boost'], 0)

    def test_a_single_cold_room_can_reject_a_reduction(self):
        c = supply.SupplyController(config(learning_mode="learn"))
        for now in range(0, 181, 30):
            update(c, now, zones=[observation(.1, 'a'), observation(.1, 'b')])
        self.assertIsNotNone(c.probe)
        for now in (210, 240, 270):
            result = update(c, now, zones=[observation(.1, 'a'), observation(.6, 'b')])
        self.assertIsNone(c.probe)
        self.assertEqual(c.corrections, [0] * 5)
        self.assertEqual(result['supply_events'][-1]['result'], 'probe_rejected')

    def test_downward_trial_is_committed_only_after_observation(self):
        c = supply.SupplyController(config(learning_mode="learn"))
        for now in range(0, 181, 30):
            result = update(c, now)
        self.assertEqual(result['supply_target'], 31.5)
        self.assertEqual(result['supply_learned_correction'], 0)
        self.assertEqual(result['supply_probe_adjustment'], -.5)
        self.assertEqual(c.corrections[2], 0)
        for now in range(210, 301, 30):
            update(c, now)
        self.assertEqual(c.corrections[2], -.5)
        self.assertIsNone(c.probe)

    def test_upward_trial_must_improve_comfort(self):
        c = supply.SupplyController(config(learning_mode="learn"))
        for now in range(0, 181, 30):
            update(c, now, deficit=.7)
        self.assertEqual(c.probe['direction'], 1)
        for now in range(210, 301, 30):
            update(c, now, deficit=.3)
        self.assertEqual(c.corrections[2], .5)

    def test_recovery_interrupts_trial_and_does_not_become_learning(self):
        c = supply.SupplyController(config(learning_mode="learn"))
        for now in range(0, 181, 30):
            update(c, now)
        for now in range(210, 301, 30):
            update(c, now, deficit=2)
        self.assertIsNone(c.probe)
        self.assertEqual(c.corrections[2], 0)
        self.assertGreater(c.boost, 0)

    def test_no_control_no_history_and_missing_room_data_cannot_train(self):
        for flags in ({'controlled': False}, {'running': False},
                      {'zones': [dict(observation(), eligible=False, air=None)]},
                      {'output_ok': False}):
            c = supply.SupplyController(config(learning_mode="learn"))
            for now in range(0, 601, 30):
                update(c, now, **flags)
            self.assertIsNone(c.probe)
            self.assertEqual(c.experience, [0] * 5)

    def test_fault_in_one_room_freezes_common_learning_without_stopping_target(self):
        c = supply.SupplyController(config(learning_mode="learn"))
        for now in range(0, 661, 30):
            result = update(c, now, deficit=2)
        self.assertIn('zone:room:insufficient_response', result['supply_faults'])
        self.assertEqual(result['supply_learning_status'], 'suspected_fault')
        self.assertIsNotNone(result['supply_target'])
        self.assertEqual(c.corrections[2], 0)
        for now in range(690, 901, 30):
            result = update(c, now, deficit=.1)
        self.assertEqual(result['supply_faults'], [])

    def test_gaps_do_not_fabricate_heating_hours_or_successful_trials(self):
        c = supply.SupplyController(config(learning_mode="learn"))
        for now in range(0, 181, 30):
            update(c, now)
        result = update(c, 10000)
        self.assertIsNone(c.probe)
        self.assertEqual(c.corrections[2], 0)
        self.assertEqual(result['supply_events'][-1]['reason'], 'observation_gap')

    def test_restart_preserves_only_committed_values_and_resets_observations(self):
        c = supply.SupplyController(config(learning_mode="learn"))
        c.corrections[1] = .5
        for now in range(0, 181, 30):
            update(c, now)
        stored = c.snapshot()
        restored = supply.SupplyController(c.config)
        restored.restore(stored, 10000)
        self.assertEqual(restored.corrections, [0, .5, 0, 0, 0])
        self.assertIsNone(restored.probe)
        result = update(restored, 10000)
        self.assertEqual(result['supply_learning_status'], 'insufficient_activation_history')

    def test_manual_point_changes_reset_only_affected_learning_geometry_resets_all(self):
        c = supply.SupplyController(config(learning_mode="learn"))
        c.corrections = [.5] * 5
        stored = c.snapshot()
        changed = deepcopy(c.config)
        changed['supply_points'][2] = 33
        fresh = supply.SupplyController(changed)
        fresh.restore(stored, 0)
        self.assertEqual(fresh.corrections, [.5, .5, 0, .5, .5])
        changed['supply_points'] = [40, 32, 24]
        fresh.configure(changed, 0)
        self.assertEqual(fresh.corrections, [0, 0, 0])

    def test_monotonic_constraints_prevent_local_inversion(self):
        c = supply.SupplyController(config(supply_points=[35, 35, 35]))
        self.assertEqual(c._trial_value(1, 1), 35)
        self.assertEqual(c._trial_value(1, -1), 35)

    def test_tracking_uses_averaged_actual_target_and_optional_return(self):
        c = supply.SupplyController(config())
        for now in range(0, 661, 30):
            result = update(c, now, supply=40 + (4 if now % 60 else -4), delivered_target=40)
        self.assertNotIn('supply_tracking', result['supply_faults'])
        self.assertIsNone(result['supply_delta_t'])
        c = supply.SupplyController(config())
        for now in range(0, 661, 30):
            result = update(c, now, supply=45, delivered_target=32, return_temperature=20)
        self.assertIn('supply_tracking', result['supply_faults'])
        self.assertIn('large_delta_t', result['supply_faults'])

    def test_validation_rejects_unusable_or_unsupported_config(self):
        for changes in ({'outdoor_sensor': None}, {'supply_points': [30]},
                        {'supply_points': [30, 40]}, {'supply_points': [float('nan'), 20]},
                        {'outdoor_min': 15}, {'heating_max': 10},
                        {'cooling_strategy': 'weather_compensated'}, {'trend_seconds': 0},
                        {'boost_enabled': 'false'}, {'typo': 1}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                supply.normalize_supply_config(config(**changes))

    def test_cycle_off_slots_pause_a_trial_and_do_not_erase_valid_learning(self):
        c = supply.SupplyController(config(learning_mode="learn", fault_seconds=3600))
        for now in range(0, 181, 30):
            update(c, now)
        self.assertIsNotNone(c.probe)
        for now in range(210, 301, 30):
            result = update(c, now, running=False)
        self.assertEqual(result['supply_learning_status'], 'probe_paused')
        self.assertEqual(c.probe['observed_seconds'], 0)
        self.assertEqual(c.corrections[2], 0)
        for now in range(330, 571, 30):
            update(c, now)
        self.assertEqual(c.corrections[2], -.5)

    def test_boost_survives_normal_cycle_off_until_comfort_recovers(self):
        c = supply.SupplyController(config())
        for now in range(0, 181, 30):
            update(c, now, deficit=2)
        boost = c.boost
        self.assertGreater(boost, 0)
        for now in range(210, 301, 30):
            update(c, now, deficit=2, running=False)
        self.assertEqual(c.boost, boost)
        for now in range(330, 541, 30):
            update(c, now, deficit=.1, running=False)
        self.assertEqual(c.boost, 0)

    def test_four_day_slow_plant_with_on_off_cycles_can_validate_learning(self):
        # Deliberately simplified thermal double with separate slab and air inertia.
        # It validates lifecycle/timing, not the calibration of a real building.
        c = supply.SupplyController(config(
            learning_mode="learn",
            sample_seconds=60, max_gap_seconds=180, trend_seconds=3600,
            learning_seconds=6 * 3600, probe_seconds=6 * 3600,
            fault_seconds=12 * 3600, recovery_seconds=7200,
            boost_rate_per_hour=1, comfort_persistence_seconds=1800))
        air, slab, target = 21.9, 28., 32.
        for now in range(0, 4 * 86400 + 1, 60):
            on = now % 600 < 300
            slab += ((target if on else air) - slab) * 60 / (7200 if on else 14400)
            air += ((slab - air) * .15 - air * .04545) * 60 / 3600
            result = update(c, now, zones=[dict(observation(), air=air, deficit=22-air, on=on)],
                            running=on, delivered_target=target)
            target = result['supply_target']
            self.assertTrue(20 <= target <= 45)
        accepted = [event for event in c.events if event['result'] == 'probe_accepted']
        self.assertGreaterEqual(len(accepted), 2)
        self.assertTrue(any(event.get('direction') == 1 for event in c.events))
        self.assertTrue(any(event.get('direction') == -1 for event in c.events))
        self.assertEqual(result['supply_faults'], [])
        self.assertLess(abs(22-air), .5)


if __name__ == '__main__':
    unittest.main()
