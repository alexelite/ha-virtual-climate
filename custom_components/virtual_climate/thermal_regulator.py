"""Per-entry HA adapter for independently stored observational zone models."""
import logging
import time

from homeassistant.helpers.storage import Store

from .thermal_control import STRATEGIES, ThermalZone

_LOGGER = logging.getLogger(__name__)


class ThermalRegulator:
    def __init__(self, hass, entry_id):
        self.hass = hass
        self.store = Store(hass, 1, f"virtual_climate.{entry_id}.thermal_zones")
        self.zones = {}
        self.fingerprints = {}
        self.diagnostics = {}
        self.decisions = {}
        self.last_save = 0.
        self.saved = {}
        self.strategy = "legacy"

    async def async_start(self, options):
        try:
            data = await self.store.async_load()
            self.saved = data if isinstance(data, dict) else {}
        except (OSError, ValueError, TypeError):
            _LOGGER.exception("Could not load thermal zone learning")
        self.configure(options)

    def configure(self, options):
        strategy = options.get("heating_control_strategy", "legacy")
        if strategy not in STRATEGIES:
            raise ValueError("Unknown heating control strategy")
        if strategy != self.strategy:
            for zone in self.zones.values():
                zone.balance = zone.integral = 0.
                zone.previous_demand = 0.
            self.strategy = strategy
        configured = {z["id"]: z for z in options.get("zones", [])}
        for zid in self.zones.keys() - configured.keys():
            del self.zones[zid]
            self.fingerprints.pop(zid, None)
            self.diagnostics.pop(zid, None)
            self.decisions.pop(zid, None)
        for zid, config in configured.items():
            fingerprint = {key: config.get(key) for key in (
                "thermal_profile", "thermal_parameters", "sensor_air", "sensor_floor", "switch_actuator",
                "temperature_filter_enabled", "open_s", "close_s", "zone_min_on_s", "zone_min_off_s", "floor_limits")}
            fingerprint["entry_parameters"] = options.get("thermal_parameters", {})
            fingerprint["supply_sensor"] = options.get("supply_control", {}).get("supply_sensor")
            fingerprint["source_entity"] = options.get("heating_source_entity")
            if options.get("circuit_control", "direct") == "external":
                fingerprint["circuit_demand_entity"] = options.get("circuit_demand_entity")
            fingerprint["pump_entity"] = options.get("circulation_pump_entity")
            if self.fingerprints.get(zid) == fingerprint:
                continue
            parameters = dict(options.get("thermal_parameters", {}))
            parameters.update(config.get("thermal_parameters", {}))
            model = ThermalZone(config.get("thermal_profile", "underfloor"), parameters)
            saved = self.saved.get(zid, {})
            if not isinstance(saved, dict):
                saved = {}
            if saved.get("fingerprint") == fingerprint:
                try:
                    model.restore(saved.get("model"))
                except (ValueError, TypeError, OverflowError):
                    _LOGGER.warning("Invalid saved thermal model for %s; using initial profile", zid)
            self.zones[zid] = model
            self.fingerprints[zid] = fingerprint

    def minimum_pulse(self, options, zone):
        minimum = float(zone.get("limits", {}).get("zone_min_on_s", 180)) + float(zone.get("actuator", {}).get("open_s", 20))
        if options.get("circuit_control", "direct") == "external":
            minimum = max(minimum, max(float(zone.get("actuator", {}).get("open_s", 20)),
                          float(options.get("external_start_delay_seconds", 0))) +
                          float(options.get("minimum_run_time_seconds", 300)) +
                          float(options.get("external_post_run_seconds", 120)))
        elif options.get("heating_source_entity") or options.get("circulation_pump_entity"):
            minimum = max(minimum, float(zone.get("actuator", {}).get("open_s", 20)) +
                          float(options.get("pump_start_delay_seconds", 0)) +
                          float(options.get("heating_source_start_delay_seconds", 30)) +
                          float(options.get("minimum_run_time_seconds", 300)) +
                          float(options.get("pump_post_run_seconds", 120)))
        return minimum

    def update(self, options, zid, zone, now, on, proportional, blocked, supply, reference, mode):
        model = self.zones.get(zid)
        if model is None or self.strategy == "legacy":
            return None
        mismatch = on is not None and on != zone.get("commanded_on", on)
        suspect = bool(zone.get("thermal_response_suspect"))
        measured = zone.get("temperature_source") == "measured"
        valid = measured and mode == "HEAT"
        blocked = blocked or not valid or zone.get("manual_off") or not zone.get("eligible_window", True)
        max_cycle = max(1., float(options.get("t_cycle_max", 1440)))
        pulse_minimum = self.minimum_pulse(options, zone)
        model.account(now, on, max_cycle)
        target = zone.get("control_setpoint")
        if target is None and zone.get("t_air") is not None and zone.get("delta_air") is not None:
            target = zone["t_air"] + zone["delta_air"]
        # Explicit commands and interlocks invalidate the balance immediately.
        # Model and integral sampling remain on a one-minute clock.
        if blocked:
            model.balance = 0.
            model.previous_demand = 0.
        if model.last_target is not None and target != model.last_target:
            model.balance = 0.
            if target is None or target < model.last_target:
                model.integral = 0.
        due = model.last_time is None or now - model.last_time >= 60 or now < model.last_time
        if due:
            target = zone.get("control_setpoint")
            if target is None and zone.get("t_air") is not None and zone.get("delta_air") is not None:
                target = zone["t_air"] + zone["delta_air"]
            decision = model.update(now, zone.get("t_air") if valid else None, target, on, proportional,
                blocked=blocked, supply=supply, reference=reference, learn=not mismatch and not suspect,
                stable=not suspect and not mismatch, max_balance=max_cycle, minimum_pulse=pulse_minimum, max_pulse=max_cycle,
                minimum_off=max(float(options.get("minimum_off_time_seconds", 180)),
                    float(zone.get("limits", {}).get("zone_min_off_s", 180)) + float(zone.get("actuator", {}).get("close_s", 20))),
                restart_wait=zone.get("restart_wait_seconds", 0), on_for=zone.get("on_for_seconds", 0))
            self.decisions[zid] = decision
        decision = dict(self.decisions.get(zid, dict(proposal=0., pulse_on=False, pulse_seconds=0.)))
        pulse = (model.balance > 0 if on is True else model.balance >= pulse_minimum)
        decision.update(pulse_on=pulse, pulse_seconds=min(max_cycle, max(pulse_minimum, model.balance)) if pulse else 0.)
        if blocked or pulse_minimum > max_cycle:
            decision.update(pulse_on=False, pulse_seconds=0.)
            if pulse_minimum > max_cycle:
                model.reason = "minimum_pulse_exceeds_cycle_limit"
        self.diagnostics[zid] = dict(model.diagnostics(), strategy=self.strategy,
                                     actual_actuator_on=on, source_context="controlled" if options.get("heating_source_entity") or options.get("circuit_demand_entity") else "independent",
                                     pump_software_state=self._state(options.get("circulation_pump_entity")),
                                     source_request_software_state=self._state(options.get("circuit_demand_entity") or options.get("heating_source_entity")),
                                     minimum_pulse_seconds=pulse_minimum, proposed_pulse_on=decision["pulse_on"])
        return decision

    def _state(self, entity):
        value = self.hass.states.get(entity) if entity else None
        return value.state if value else None

    async def async_save(self, force=False):
        now = time.time()
        if force or now - self.last_save >= 900:
            await self.store.async_save({zid: dict(fingerprint=self.fingerprints[zid], model=z.snapshot())
                                        for zid, z in self.zones.items()})
            self.last_save = now

    async def async_learn(self):
        # Identification is CPU work; never block Home Assistant's event loop.
        now = time.time()
        for model in self.zones.values():
            if now - model._last_fit >= 6 * 3600 and model.valid_seconds >= 7 * 86400:
                snapshot = model.snapshot()
                candidate = ThermalZone(model.profile, model.config)
                candidate.restore(snapshot)
                accepted = await self.hass.async_add_executor_job(candidate.fit, now)
                model._last_fit = now
                model.validation = candidate.validation
                if accepted:
                    model.parameters = candidate.parameters
                    model.validated = True
                    model.reset_transient()
