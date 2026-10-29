"""Home Assistant I/O for supply policy: sensors, delivery, storage and alerts."""
from __future__ import annotations

import asyncio
import logging
import time

from homeassistant.helpers.storage import Store

from .supply_control import SupplyController, finite, normalize_supply_config
from .const import THERMAL_UPDATE_SECONDS

_LOGGER = logging.getLogger(__name__)


class SupplyRegulator:
    """Driven by the coordinator; owns the only supply-temperature writer."""

    def __init__(self, hass, entry_id):
        self.hass, self.entry_id = hass, entry_id
        self.controller = SupplyController()
        self.store = Store(hass, 1, f"virtual_climate.{entry_id}.supply")
        self._last_update = self._last_mode = self._last_write = None
        self._last_attempt = self._last_save = None
        self._saved_revision = -1
        self._write_lock = asyncio.Lock()
        self._notified = None
        self._saved_event = None
        self.command_error = None
        self.diagnostics = {}

    def _config(self, options):
        value = options.get("supply_control")
        if value is None:
            # Legacy fixed targets retain their previously configured range.
            value = {"heating_min": 0.0, "heating_max": 90.0,
                     "cooling_min": 0.0, "cooling_max": 90.0}
        config = normalize_supply_config(value)
        # Old exports may specify 30 seconds; the integration now samples rooms
        # once a minute, so learning must use the same effective sample cadence.
        config["sample_seconds"] = max(THERMAL_UPDATE_SECONDS, config["sample_seconds"])
        config["max_gap_seconds"] = max(2 * config["sample_seconds"], config["max_gap_seconds"])
        for key in ("trend_seconds", "fault_seconds", "recovery_seconds", "learning_seconds", "probe_seconds"):
            config[key] = max(2 * config["sample_seconds"], config[key])
        return config

    async def async_start(self, options):
        self.controller.configure(self._config(options), time.time())
        try:
            self.controller.restore(await self.store.async_load(), time.time())
        except (OSError, ValueError, TypeError):
            _LOGGER.exception("Could not restore supply learning for %s", self.entry_id)

    async def async_stop(self):
        self.controller.cancel_probe(time.time(), "integration_stopped")
        await self.store.async_save(self.controller.snapshot())

    def _temperature(self, entity_id, now):
        state = self.hass.states.get(entity_id) if entity_id else None
        value = finite(state.state) if state else None
        if value is None:
            return None
        age = self.controller.config["sensor_max_age_seconds"]
        reported = getattr(state, "last_reported", None) or getattr(state, "last_updated", None)
        if age and (reported is None or now - reported.timestamp() > age):
            return None
        unit = state.attributes.get("unit_of_measurement")
        if unit in ("°F", "F"):
            value = (value - 32) * 5 / 9
        elif unit in ("K", "°K"):
            value -= 273.15
        elif unit not in (None, "°C", "C"):
            return None
        return value if -80 <= value <= 120 else None

    async def async_update(self, options, mode, zones, *, controlled, running, force=False):
        now = time.time()
        config = self._config(options)
        changed = config != self.controller.config
        self.controller.configure(config, now)
        if not force and not changed and self._last_mode == mode and self._last_update is not None and (
            0 <= now - self._last_update < config["sample_seconds"]
        ):
            return self.diagnostics
        self._last_update, self._last_mode = now, mode
        observations = []
        configured = {z["id"]: z for z in options.get("zones", [])}
        for zid in sorted(configured.keys() | zones.keys()):
            zone, zconfig = zones.get(zid, {}), configured.get(zid, {})
            state = self.hass.states.get(zone.get("actuator", {}).get("entity_id") or zconfig.get("switch_actuator"))
            air_entity = zconfig.get("sensor_air")
            air = self._temperature(air_entity, now) if air_entity else finite(zone.get("t_air"))
            delta = finite(zone.get("delta_air"))
            published_air = finite(zone.get("t_air"))
            sampled_at = finite(zone.get("temperature_sampled_at"))
            if sampled_at is not None:
                # Use the same filtered room temperature as zone demand. Still
                # validate the source so a vanished/stale sensor is not masked.
                valid_sample = (0 <= now - sampled_at <= config["max_gap_seconds"]
                                and zone.get("air_sensor_entity_id") == air_entity)
                air = published_air if air is not None and valid_sample else None
            elif air is not None and delta is not None and published_air is not None:
                # Preserve the published setpoint when a sensor changed since the
                # legacy zone status publication (without sampling metadata).
                delta = published_air + delta - air
            expected = not (zone.get("manual_off") or zone.get("window_open") or
                            not zone.get("eligible_window", True) or
                            zone.get("support_mode", "BOTH") not in (mode, "BOTH") or
                            set(zone.get("last_block_reasons", [])) & {
                                "floor_heat_max", "floor_cool_min", "rh_fault", "dew_guard_lockout"})
            observations.append({"id": zid, "air": air, "deficit": delta, "expected": expected,
                                 "eligible": expected and air is not None and delta is not None
                                 and state is not None and state.state in ("on", "off"),
                                 "on": bool(state and state.state == "on")})
        fixed = float(options.get("cooling_supply_target" if mode == "COOL" else "heating_supply_target",
                                  18.0 if mode == "COOL" else 32.0))
        entity = options.get("target_supply_temperature_entity")
        target_state = self.hass.states.get(entity) if entity else None
        ready = bool(target_state and finite(target_state.state) is not None)
        if entity and not ready:
            self.command_error = "target_unavailable"
        elif not entity and controlled and mode == "HEAT" and config["heating_strategy"] == "weather_compensated":
            self.command_error = "target_not_configured"
        outdoor = self._temperature(config["outdoor_sensor"], now)
        if outdoor is not None and not -80 <= outdoor <= 60:
            outdoor = None
        self.diagnostics = self.controller.update(
            now, mode, fixed, outdoor, observations,
            controlled=controlled, running=running,
            output_ok=bool(entity and ready and self.command_error is None and self._last_write is not None
                           and self._last_write[0] == (mode, entity)),
            supply=self._temperature(config["supply_sensor"], now),
            return_temperature=self._temperature(config["return_sensor"], now),
            delivered_target=self._last_write[1] if self._last_write and self._last_write[0] == (mode, entity) else None,
            monitoring_ok=self.command_error is None)
        self.diagnostics["supply_command_error"] = self.command_error
        self.diagnostics["supply_last_write"] = self._last_write[1] if self._last_write else None
        await self._notify()
        last_event = dict(self.controller.events[-1]) if self.controller.events else None
        if self.controller.revision != self._saved_revision and (
            self._last_save is None or now - self._last_save >= 300 or last_event != self._saved_event
        ):
            snapshot = self.controller.snapshot()
            self.store.async_delay_save(lambda: snapshot, 1)
            self._saved_revision, self._last_save = self.controller.revision, now
            self._saved_event = last_event
        return self.diagnostics

    async def async_write(self, options, mode, *, force=False):
        """Confirm service completion, without waiting for water convergence."""
        entity = options.get("target_supply_temperature_entity")
        if not entity:
            if mode == "HEAT" and self.controller.config["heating_strategy"] == "weather_compensated":
                self.command_error = "target_not_configured"
                self._last_attempt = time.time()
                self.controller.cancel_probe(time.time(), "command_error")
                self.diagnostics["supply_command_error"] = self.command_error
                await self._notify()
                return False
            return True

        async with self._write_lock:
            now, c = time.time(), self.controller.config
            target = self.diagnostics.get("supply_target")
            if target is None:
                return False
            last = self._last_write
            if (not force or self.command_error is not None) and self._last_attempt is not None and now - self._last_attempt < c["write_interval_seconds"]:
                return self.command_error is None and last is not None
            if not force and last and last[0] == (mode, entity) and abs(last[1] - target) < c["write_delta"] and (
                now - last[2] < c["write_refresh_seconds"] and self.command_error is None
            ):
                return True
            self._last_attempt = now
            try:
                state = self.hass.states.get(entity)
                if entity.split(".", 1)[0] not in ("number", "input_number"):
                    raise ValueError("unsupported_target_entity")
                if state is None or finite(state.state) is None:
                    raise ValueError("target_unavailable")
                unit = state.attributes.get("unit_of_measurement")
                if unit not in (None, "°C", "C", "°F", "F"):
                    raise ValueError("unsupported_target_unit")
                command = target * 9 / 5 + 32 if unit in ("°F", "F") else target
                low, high = finite(state.attributes.get("min")), finite(state.attributes.get("max"))
                if (low is not None and command < low) or (high is not None and command > high):
                    raise ValueError("target_outside_device_limits")
                await asyncio.wait_for(self.hass.services.async_call(
                    entity.split(".", 1)[0], "set_value", {"entity_id": entity, "value": round(command, 2)},
                    blocking=True), timeout=10)
            except Exception as error:
                self.command_error = str(error) if isinstance(error, ValueError) else "target_write_failed"
                self.controller.cancel_probe(now, "command_error")
                self.diagnostics["supply_command_error"] = self.command_error
                self.diagnostics["supply_learning_status"] = "command_error"
                _LOGGER.warning("Supply command failed for %s: %s", entity, error)
                await self._notify()
                return False
            self.command_error = None
            self._last_write = ((mode, entity), target, now)
            self.diagnostics["supply_command_error"] = None
            self.diagnostics["supply_last_write"] = target
            return True

    def retry_ready(self):
        return (self.command_error is None or self._last_attempt is None or
                time.time() - self._last_attempt >= self.controller.config["write_interval_seconds"])

    async def _notify(self):
        faults = tuple(self.diagnostics.get("supply_faults", []))
        issue = (self.command_error, faults)
        if issue == self._notified:
            return
        previous_issue = self._notified
        self._notified = issue
        if not self.command_error and not faults:
            if previous_issue and (previous_issue[0] or previous_issue[1]):
                try:
                    await self.hass.services.async_call("persistent_notification", "dismiss", {
                        "notification_id": f"virtual_climate_{self.entry_id}_supply",
                    }, blocking=False)
                except Exception:
                    _LOGGER.debug("Could not dismiss resolved supply notification", exc_info=True)
            return
        message = ("Supply command: " + self.command_error if self.command_error else
                   "Persistent thermal response issue: " + ", ".join(faults) +
                   ". Check source operation and hydraulic balancing. Actuator ON does not confirm flow.")
        try:
            await self.hass.services.async_call("persistent_notification", "create", {
                "notification_id": f"virtual_climate_{self.entry_id}_supply",
                "title": "Virtual Climate — supply control", "message": message,
            }, blocking=False)
        except Exception:
            _LOGGER.debug("Could not create supply notification", exc_info=True)

    async def async_reset_learning(self):
        self.controller.reset_learning(time.time())
        await self.store.async_save(self.controller.snapshot())
        self._last_update = None
