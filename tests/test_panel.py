"""Entry-scoped supply edits, conflict detection and learning-reset previews."""
from copy import deepcopy
from hashlib import sha256
import json
from types import SimpleNamespace
import unittest

import voluptuous as vol

from support import load_source, options_flow


def panel():
    ns = options_flow()
    ns.update(deepcopy=deepcopy, sha256=sha256, json=json, schema=vol,
              websocket_api=SimpleNamespace(websocket_command=lambda _: lambda f: f,
                                            require_admin=lambda f: f))
    return load_source("panel.py", ns)


class PanelTests(unittest.TestCase):
    def setUp(self):
        self.ns = panel()
        self.entry = SimpleNamespace(domain="virtual_climate", state=SimpleNamespace(value="loaded"), data={
            "global_co_mode_entity": "input_select.mode", "zones": [{"id": "zone_a"}],
            "supply_control": {"learning_seconds": 172800},
        }, options={"packing_mode": "staggered", "heating_supply_target": 33})

    def test_partial_edit_preserves_tuning_zones_and_other_options(self):
        before = deepcopy(self.entry)
        options, preview = self.ns["prepare_change"](self.entry, {"heating_supply_target": 35})
        self.assertEqual(self.entry, before)
        self.assertEqual(options["supply_control"]["learning_seconds"], 172800)
        self.assertEqual(options["packing_mode"], "staggered")
        self.assertNotIn("zones", options)
        self.assertEqual(preview["learning_reset"], "none")
        self.assertEqual(preview["changes"], [{"key": "heating_supply_target", "before": 33, "after": 35.0}])

    def test_curve_geometry_and_individual_point_resets(self):
        _, preview = self.ns["prepare_change"](self.entry, {"supply_points": [41, 36, 32, 28, 24]})
        self.assertEqual(preview["reset_points"], [1])
        self.assertEqual(preview["learning_reset"], "points")
        for changes in ({"outdoor_min": -20}, {"supply_points": [40, 24]}):
            with self.subTest(changes=changes):
                _, preview = self.ns["prepare_change"](self.entry, changes)
                self.assertEqual(preview["learning_reset"], "all")

    def test_legacy_entry_keeps_runtime_limits_when_saved(self):
        # Entries created before supply_control run with 0-90 limits; a panel
        # edit must neither narrow them silently nor hide a change in review.
        entry = SimpleNamespace(domain="virtual_climate", data={
            "global_co_mode_entity": "input_select.mode", "zones": [{"id": "zone_a"}],
        }, options={"heating_supply_target": 55})
        settings = self.ns["settings"](self.ns["get_current_config"](entry))
        self.assertEqual((settings["heating_min"], settings["heating_max"]), (0.0, 90.0))
        options, preview = self.ns["prepare_change"](entry, {"supply_sensor": "sensor.supply"})
        self.assertEqual([c["key"] for c in preview["changes"]], ["supply_sensor"])
        supply = options["supply_control"]
        self.assertEqual((supply["heating_min"], supply["heating_max"]), (0.0, 90.0))
        self.assertEqual((supply["cooling_min"], supply["cooling_max"]), (0.0, 90.0))

    def test_rejects_invalid_and_out_of_scope_settings_without_mutation(self):
        before = deepcopy(self.entry)
        invalid = ({"zones": []}, {"heating_strategy": "weather_compensated"},
                   {"supply_points": [20, 30]}, {"heating_supply_target": float("nan")},
                   {"target_supply_temperature_entity": "switch.source"},
                   {"outdoor_min": 20, "outdoor_max": 10}, {"boost_enabled": "false"})
        for changes in invalid:
            with self.subTest(changes=changes), self.assertRaises((ValueError, TypeError)):
                self.ns["prepare_change"](self.entry, changes)
        self.assertEqual(self.entry, before)

    def test_revision_covers_other_flow_edits_and_other_entries_stay_independent(self):
        revision = self.ns["revision"](self.entry)
        other = deepcopy(self.entry)
        other.options["packing_mode"] = "simultaneous"
        self.assertNotEqual(revision, self.ns["revision"](other))
        self.assertEqual(revision, self.ns["revision"](self.entry))

    def test_validate_noop_save_and_stale_save_have_no_side_effects(self):
        updates, errors, results = [], [], []
        entries = SimpleNamespace(async_get_entry=lambda _: self.entry,
                                  async_update_entry=lambda entry, **kw: updates.append(kw))
        hass = SimpleNamespace(config_entries=entries)
        connection = SimpleNamespace(send_error=lambda *args: errors.append(args),
                                     send_result=lambda *args: results.append(args))
        msg = {"id": 1, "entry_id": "a", "revision": self.ns["revision"](self.entry),
               "changes": {"heating_supply_target": 35}}
        self.ns["_change"](hass, connection, msg, save=False)
        self.assertFalse(updates)
        self.assertEqual(results[-1][1]["settings"]["heating_supply_target"], 35)
        self.ns["_change"](hass, connection, {**msg, "changes": {}}, save=True)
        self.assertFalse(updates)
        self.entry.options["packing_mode"] = "simultaneous"
        self.ns["_change"](hass, connection, msg, save=True)
        self.assertEqual(errors[-1][1], "conflict")
        self.assertFalse(updates)
        msg["revision"] = self.ns["revision"](self.entry)
        self.ns["_change"](hass, connection, msg, save=True)
        self.assertEqual(len(updates), 1)
        self.assertEqual(updates[0]["options"]["heating_supply_target"], 35)

    def test_save_waits_until_entry_reload_finishes(self):
        self.entry.state.value = "setup_in_progress"
        errors = []
        hass = SimpleNamespace(config_entries=SimpleNamespace(async_get_entry=lambda _: self.entry))
        connection = SimpleNamespace(send_error=lambda *args: errors.append(args))
        self.ns["_change"](hass, connection, {
            "id": 1, "entry_id": "a", "revision": self.ns["revision"](self.entry),
            "changes": {"heating_supply_target": 35},
        }, save=True)
        self.assertEqual(errors[-1][1], "not_ready")


class PanelZoneTests(unittest.TestCase):
    def setUp(self):
        self.ns = panel()
        self.zone = {"id": "zone_a", "name": "Living", "sensor_air": "sensor.living", "sensor_rh": "sensor.living_rh",
                     "switch_actuator": "switch.living", "thermal_parameters": {}, "custom_key": 7}
        self.entry = SimpleNamespace(domain="virtual_climate", state=SimpleNamespace(value="loaded"), data={
            "global_co_mode_entity": "input_select.mode",
            "zones": [self.zone, {"id": "zone_b", "name": "Bed", "sensor_air": "sensor.bed",
                                  "switch_actuator": "switch.bed"}],
        }, options={"packing_mode": "staggered"})

    def test_zone_edit_changes_only_that_zone_and_keeps_unknown_keys(self):
        before = deepcopy(self.entry)
        options, preview = self.ns["prepare_zone_change"](self.entry, "zone_a", {
            "name": "Living room", "floor_heat_max": 29, "sensor_rh": None})
        self.assertEqual(self.entry, before)
        zones = {zone["id"]: zone for zone in options["zones"]}
        self.assertEqual(zones["zone_a"]["name"], "Living room")
        self.assertEqual(zones["zone_a"]["floor_limits"], {"heat_max": 29.0})
        self.assertIsNone(zones["zone_a"]["sensor_rh"])
        self.assertEqual(zones["zone_a"]["custom_key"], 7)
        self.assertEqual(zones["zone_b"]["name"], "Bed")
        self.assertEqual(options["packing_mode"], "staggered")
        self.assertEqual({c["key"] for c in preview["changes"]}, {"name", "floor_heat_max", "sensor_rh"})

    def test_noop_zone_edit_reports_no_changes(self):
        _, preview = self.ns["prepare_zone_change"](self.entry, "zone_a", {})
        self.assertEqual(preview["changes"], [])

    def test_invalid_zone_edits_are_rejected(self):
        invalid = ({"sensor_air": None}, {"switch_actuator": "light.x"}, {"support_mode": "AUTO"},
                   {"open_s": -1}, {"open_s": 1.5}, {"zone_min_on_s": True}, {"floor_heat_min": 35, "floor_heat_max": 30},
                   {"floor_cool_min": 5}, {"name": " "}, {"id": "zone_c"}, {"temperature_filter_enabled": "yes"})
        for changes in invalid:
            with self.subTest(changes=changes), self.assertRaises((ValueError, TypeError)):
                self.ns["prepare_zone_change"](self.entry, "zone_a", changes)
        with self.assertRaises(KeyError):
            self.ns["prepare_zone_change"](self.entry, "missing", {})

    def test_full_config_shows_effective_supply_limits(self):
        config = self.ns["full_config"](self.ns["get_current_config"](self.entry))
        self.assertEqual(config["global"]["supply_control"]["heating_max"], 90.0)
        self.assertEqual([zone["id"] for zone in config["zones"]], ["zone_a", "zone_b"])
