import math
import unittest

from support import filter_module


class TemperatureFilterTests(unittest.TestCase):
    def test_step_response_uses_elapsed_seconds(self):
        f = filter_module.TemperatureFilter()
        self.assertEqual(f.update(20, 0, source='a'), 20)
        self.assertAlmostEqual(f.update(21, 60, source='a'), 20 + 1 - math.exp(-1 / 3))
        self.assertAlmostEqual(f.update(21, 180, source='a'), 20 + 1 - math.exp(-1))

    def test_frequent_calls_do_not_add_weight(self):
        dense, sparse = filter_module.TemperatureFilter(), filter_module.TemperatureFilter()
        for f in (dense, sparse):
            f.update(20, 0, source='a')
        for t in range(5, 60, 5):
            self.assertEqual(dense.update(21, t, source='a'), 20)
        self.assertEqual(dense.update(21, 60, source='a'), sparse.update(21, 60, source='a'))

    def test_control_clock_jitter_still_uses_actual_elapsed_time(self):
        f = filter_module.TemperatureFilter()
        f.update(20, 0, source='a')
        self.assertAlmostEqual(f.update(21, 59.98, source='a', control_sample=True),
                               21 - math.exp(-59.98 / 180))

    def test_disabled_filter_and_reenable_start_from_measured_temperature(self):
        f = filter_module.TemperatureFilter()
        f.update(20, 0, source='a')
        self.assertEqual(f.update(21, 60, source='a', enabled=False), 21)
        self.assertEqual(f.update(22, 120, source='a', enabled=True), 22)

    def test_unavailable_cannot_be_hidden_by_previous_value(self):
        for value in (None, float('nan'), float('inf')):
            with self.subTest(value=value):
                f = filter_module.TemperatureFilter()
                f.update(20, 0, source='a')
                self.assertIsNone(f.update(value, 60, source='a'))
                self.assertEqual(f.update(23, 120, source='a'), 23)

    def test_source_change_long_gap_and_clock_rollback_reset(self):
        for t, source in ((60, 'b'), (301, 'a'), (-1, 'a')):
            with self.subTest(t=t, source=source):
                f = filter_module.TemperatureFilter()
                f.update(20, 0, source='a')
                self.assertEqual(f.update(23, t, source=source), 23)
