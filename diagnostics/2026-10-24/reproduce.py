"""Rerun the original coordinator symptoms against the production regression seam.

Run: python3 diagnostics/2026-10-24/reproduce.py
Exit 0 means these original defects no longer reproduce. No live HA calls.
"""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tests'))

CASES = (
    'test_zone_turns_off_at_slot_end',
    'test_full_demand_continues_across_cycle_boundary',
    'test_cycle_rollover_does_not_publish_zero_or_stop',
    'test_demand_remains_positive_during_restart_lockout',
    'test_real_off_requires_full_restart_delay',
    'test_pending_feedback_is_not_counted_as_running',
)
suite = unittest.TestSuite(
    unittest.defaultTestLoader.loadTestsFromName(f'test_zone_manager.ZoneManagerTests.{case}')
    for case in CASES
)
result = unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(not result.wasSuccessful())
