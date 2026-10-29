"""Supply-temperature policy, independent of Home Assistant I/O.

All temperatures and rates use Celsius and Celsius/hour. Observations describe
reported electrical activation, never inferred water flow or delivered power.
"""
from __future__ import annotations

from bisect import bisect_right
from collections import deque
from copy import deepcopy
import math


SUPPLY_DEFAULTS = {
    "heating_strategy": "constant", "cooling_strategy": "constant",
    "outdoor_sensor": None, "supply_sensor": None, "return_sensor": None,
    "outdoor_min": -15.0, "outdoor_max": 15.0,
    "supply_points": [40.0, 36.0, 32.0, 28.0, 24.0],
    "heating_min": 20.0, "heating_max": 45.0,
    "cooling_min": 5.0, "cooling_max": 30.0,
    "learning_mode": "off", "boost_enabled": True,
    "sample_seconds": 60.0, "max_gap_seconds": 120.0,
    "sensor_max_age_seconds": 0.0, "trend_seconds": 3600.0,
    "fault_seconds": 21600.0, "recovery_seconds": 7200.0,
    "learning_seconds": 86400.0, "probe_seconds": 86400.0,
    "learning_step": 0.5, "correction_limit": 5.0,
    "comfort_tolerance": 0.3, "boost_deficit": 1.0,
    "boost_gain": 2.0, "boost_max": 5.0, "boost_rate_per_hour": 1.0,
    "minimum_recovery_rate": 0.1, "minimum_active_fraction": 0.2,
    "supply_tolerance": 5.0, "delta_t_alert": 15.0,
    "write_interval_seconds": 60.0, "write_delta": 0.2,
    "write_refresh_seconds": 900.0,
    "probe_outdoor_tolerance": 2.0,
    "comfort_persistence_seconds": 1800.0, "minimum_learning_improvement": 0.05,
}


def finite(value):
    """Return a finite numeric value, excluding bools and missing states."""
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if math.isfinite(result) else None


def normalize_supply_config(value=None):
    """Validate both imports and options; reject unknown keys and NaN."""
    if value is not None and not isinstance(value, dict):
        raise ValueError("supply_control must be an object")
    value = value or {}
    if set(value) - set(SUPPLY_DEFAULTS):
        raise ValueError("Unknown supply_control setting")
    config = deepcopy(SUPPLY_DEFAULTS)
    config.update(deepcopy(value))
    if config["heating_strategy"] not in ("constant", "weather_compensated"):
        raise ValueError("Invalid heating strategy")
    if config["cooling_strategy"] != "constant":
        raise ValueError("Weather compensation for cooling is not supported yet")
    if config["learning_mode"] not in ("off", "learn", "frozen"):
        raise ValueError("Invalid learning mode")
    if not isinstance(config["boost_enabled"], bool):
        raise ValueError("boost_enabled must be boolean")
    for key in ("outdoor_sensor", "supply_sensor", "return_sensor"):
        entity = config[key]
        if entity in (None, ""):
            config[key] = None
        elif not isinstance(entity, str) or not entity.startswith("sensor."):
            raise ValueError(f"{key} must be a sensor entity")
    if config["heating_strategy"] == "weather_compensated" and not config["outdoor_sensor"]:
        raise ValueError("Weather compensation requires an outdoor sensor")
    points = config["supply_points"]
    if not isinstance(points, list) or not 2 <= len(points) <= 50:
        raise ValueError("Provide 2 to 50 supply points")
    config["supply_points"] = [finite(point) for point in points]
    if any(point is None or not 0 <= point <= 90 for point in config["supply_points"]):
        raise ValueError("Supply points must be finite temperatures between 0 and 90")
    if any(a < b for a, b in zip(config["supply_points"], config["supply_points"][1:])):
        raise ValueError("Heating supply must not increase with outdoor temperature")
    for key, default in SUPPLY_DEFAULTS.items():
        if not isinstance(default, float):
            continue
        number = finite(config[key])
        if number is None:
            raise ValueError(f"{key} must be finite")
        config[key] = number
        if key not in ("outdoor_min", "outdoor_max") and number < 0:
            raise ValueError(f"{key} must not be negative")
        if key.endswith("seconds") and number > 7 * 86400:
            raise ValueError(f"{key} must not exceed seven days")
    if not -80 <= config["outdoor_min"] < config["outdoor_max"] <= 60:
        raise ValueError("Invalid outdoor interval")
    for mode in ("heating", "cooling"):
        if not 0 <= config[f"{mode}_min"] < config[f"{mode}_max"] <= 90:
            raise ValueError("Invalid supply temperature limits")
    if config["heating_strategy"] == "weather_compensated" and any(
        not config["heating_min"] <= point <= config["heating_max"] for point in config["supply_points"]
    ):
        raise ValueError("Supply points must be inside the heating limits")
    if not 0 < config["minimum_active_fraction"] <= 1:
        raise ValueError("Invalid minimum active fraction")
    if not 30 <= config["sample_seconds"] <= 300:
        raise ValueError("Sampling interval must be between 30 and 300 seconds")
    if config["max_gap_seconds"] < 2 * config["sample_seconds"]:
        raise ValueError("Maximum observation gap must cover two samples")
    for key in ("trend_seconds", "fault_seconds", "recovery_seconds", "learning_seconds", "probe_seconds"):
        if config[key] < 2 * config["sample_seconds"]:
            raise ValueError(f"{key} must cover at least two sample intervals")
    for key in ("learning_step", "comfort_tolerance", "boost_deficit", "boost_rate_per_hour",
                "minimum_recovery_rate", "supply_tolerance", "write_interval_seconds",
                "write_delta", "write_refresh_seconds"):
        if config[key] <= 0:
            raise ValueError(f"{key} must be positive")
    if config["learning_step"] > config["correction_limit"]:
        raise ValueError("Learning step exceeds correction limit")
    if config["comfort_tolerance"] >= config["boost_deficit"]:
        raise ValueError("Boost threshold must exceed comfort tolerance")
    return config


def curve_axes(config):
    n = len(config["supply_points"])
    return [config["outdoor_min"] + i * (config["outdoor_max"] - config["outdoor_min"]) / (n - 1)
            for i in range(n)]


def interpolate(xs, ys, temperature):
    """Linear interpolation, continuing the end segment outside the domain."""
    index = max(0, min(len(xs) - 2, bisect_right(xs, temperature) - 1))
    fraction = (temperature - xs[index]) / (xs[index + 1] - xs[index])
    return ys[index] + fraction * (ys[index + 1] - ys[index])


class SupplyController:
    """Observe, explain and adjust a common supply target using bounded trials."""

    def __init__(self, config=None):
        self.config = normalize_supply_config(config)
        self.corrections = [0.0] * len(self.config["supply_points"])
        self.experience = [0.0] * len(self.corrections)
        self.revision = 0
        self.events = deque(maxlen=30)
        self.probe = None
        self._history = {}
        self._supply_history = deque()
        self._last_sample = None
        self._context = None
        self._faults = {}
        self._recovery = {}
        self._learning_elapsed = [0.0] * len(self.corrections)
        self._previous_learning_valid = False
        self.boost = 0.0
        self.diagnostics = {}

    def _event(self, now, result, **details):
        self.events.append({"time": now, "result": result, **details})
        self.revision += 1

    def configure(self, config, now):
        config = normalize_supply_config(config)
        if config == self.config:
            return
        self.cancel_probe(now, "configuration_changed")
        old = self.config
        geometry_changed = (curve_axes(old) != curve_axes(config))
        if geometry_changed:
            self.corrections = [0.0] * len(config["supply_points"])
            self.experience = [0.0] * len(self.corrections)
        else:
            for i, (a, b) in enumerate(zip(old["supply_points"], config["supply_points"])):
                if a != b:
                    self.corrections[i] = self.experience[i] = 0.0
        self.config = config
        self._constrain_corrections()
        self._clear_observations()
        self._event(now, "configuration_changed", learning_reset=geometry_changed)

    def _clear_observations(self):
        self._history.clear()
        self._supply_history.clear()
        self._last_sample = None
        self._context = None
        self._learning_elapsed = [0.0] * len(self.corrections)
        self._previous_learning_valid = False
        self.boost = 0.0

    def _constrain_corrections(self):
        """Constrain each point locally; never move a neighbour to hide a limit."""
        base = self.config["supply_points"]
        limit = self.config["correction_limit"]
        values = []
        for i, correction in enumerate(self.corrections):
            low = max(self.config["heating_min"], base[i] - limit)
            high = min(self.config["heating_max"], base[i] + limit)
            # Base coordinates can be outside the final output bounds.
            low, high = min(low, high), max(low, high)
            value = min(high, max(low, base[i] + correction))
            if values:
                value = min(value, values[-1])
            values.append(value)
        self.corrections = [value - base[i] for i, value in enumerate(values)]

    def snapshot(self):
        """Only committed corrections survive a restart; a probe is a marker."""
        return {"axes": curve_axes(self.config), "base": list(self.config["supply_points"]),
                "corrections": list(self.corrections), "experience": list(self.experience),
                "probe_interrupted": self.probe is not None, "events": list(self.events)}

    def restore(self, data, now):
        if not isinstance(data, dict):
            return
        if data.get("axes") != curve_axes(self.config):
            self._event(now, "learning_reset_geometry")
            return
        base, corrections, experience = (data.get(key) for key in ("base", "corrections", "experience"))
        n = len(self.corrections)
        if not all(isinstance(values, list) and len(values) == n for values in (base, corrections, experience)):
            return
        for i in range(n):
            correction, seconds = finite(corrections[i]), finite(experience[i])
            if base[i] == self.config["supply_points"][i] and correction is not None and seconds is not None:
                self.corrections[i] = max(-self.config["correction_limit"], min(self.config["correction_limit"], correction))
                self.experience[i] = max(0.0, seconds)
        self._constrain_corrections()
        self.events.extend(event for event in data.get("events", [])[-30:] if isinstance(event, dict))
        if data.get("probe_interrupted"):
            self._event(now, "probe_interrupted_restart")

    def reset_learning(self, now):
        self.cancel_probe(now, "manual_reset")
        self.corrections = [0.0] * len(self.corrections)
        self.experience = [0.0] * len(self.corrections)
        self._clear_observations()
        self._event(now, "learning_reset")

    def cancel_probe(self, now, reason, reset_wait=True):
        if self.probe:
            self._event(now, "probe_interrupted", reason=reason, point=self.probe["point"])
            self.probe = None
        if reset_wait:
            self._learning_elapsed = [0.0] * len(self.corrections)
            self._previous_learning_valid = False

    def _metrics(self, samples, now, window):
        rows = [row for row in samples if row[0] >= now - window]
        if len(rows) < 3 or rows[-1][0] - rows[0][0] < window * 0.9:
            return None
        span = rows[-1][0] - rows[0][0]
        active = sum((b[0] - a[0]) for a, b in zip(rows, rows[1:]) if a[3])
        center = sum(row[0] - now for row in rows) / len(rows)
        mean_air = sum(row[1] for row in rows) / len(rows)
        variance = sum((row[0] - now - center) ** 2 for row in rows)
        slope = sum((row[0] - now - center) * (row[1] - mean_air) for row in rows) / variance
        return {"rate": slope * 3600,
                "active_fraction": active / span, "active_seconds": active,
                "mean_deficit": sum(row[2] - row[1] for row in rows) / len(rows),
                "deficit": rows[-1][2] - rows[-1][1]}

    def _fault(self, now, key, bad, recovered):
        if bad:
            self._recovery.pop(key, None)
            if key not in self._faults:
                self._faults[key] = now
                self._event(now, "fault", reason=key)
        elif key in self._faults and recovered:
            started = self._recovery.setdefault(key, now)
            if now - started >= self.config["recovery_seconds"]:
                del self._faults[key]
                self._recovery.pop(key, None)
                self._event(now, "fault_cleared", reason=key)
        else:
            self._recovery.pop(key, None)

    def _trial_value(self, point, direction):
        c = self.config
        values = [a + b for a, b in zip(c["supply_points"], self.corrections)]
        original = values[point]
        low = max(c["heating_min"], c["supply_points"][point] - c["correction_limit"])
        high = min(c["heating_max"], c["supply_points"][point] + c["correction_limit"])
        if point < len(values) - 1:
            low = max(low, values[point + 1])
        if point:
            high = min(high, values[point - 1])
        if low > high:
            return original
        return max(low, min(high, original + direction * c["learning_step"]))

    def update(self, now, mode, fixed_target, outdoor, zones, *, controlled=False,
               running=False, output_ok=True, supply=None, return_temperature=None,
               delivered_target=None, monitoring_ok=True, fallback_active=False):
        """Evaluate one sample. Missing/gapped observations never accrue time."""
        c = self.config
        weather = mode == "HEAT" and c["heating_strategy"] == "weather_compensated"
        fallback = weather and outdoor is None
        xs = curve_axes(c)
        outside = weather and outdoor is not None and not xs[0] <= outdoor <= xs[-1]
        point = min(range(len(xs)), key=lambda i: (abs(xs[i] - outdoor), i)) if weather and outdoor is not None else None
        eligible = {z["id"]: z for z in zones if z.get("eligible") and finite(z.get("air")) is not None
                    and finite(z.get("deficit")) is not None}
        valid_zones = len(eligible) == len([z for z in zones if z.get("expected")]) and bool(eligible)
        context = (mode, point, tuple(sorted((key, round(z["air"] + z["deficit"], 3)) for key, z in eligible.items())))
        if context != self._context:
            if self._context is not None and mode != self._context[0]:
                self._supply_history.clear()
            same_zones = self._context is not None and (mode, context[2]) == (self._context[0], self._context[2])
            self.cancel_probe(now, "zone_setpoint_or_interval_changed", reset_wait=not same_zones)
            self._context = context
        elapsed = 0.0 if self._last_sample is None else now - self._last_sample
        sampled = self._last_sample is None or elapsed < 0 or elapsed >= c["sample_seconds"]
        if sampled:
            if elapsed < 0 or elapsed > c["max_gap_seconds"]:
                self.cancel_probe(now, "observation_gap")
                self._history.clear()
                self._supply_history.clear()
                elapsed = 0.0
            self._last_sample = now
            keep = max(c["trend_seconds"], c["fault_seconds"])
            for key in list(self._history):
                if key not in eligible:
                    del self._history[key]
            for key, zone in eligible.items():
                rows = self._history.setdefault(key, deque())
                target = zone["air"] + zone["deficit"]
                if rows and abs(rows[-1][2] - target) > 0.01:
                    rows.clear()
                rows.append((now, zone["air"], target, bool(zone.get("on") and running and controlled and monitoring_ok)))
                while rows and rows[0][0] < now - keep - c["sample_seconds"]:
                    rows.popleft()
            if running and controlled and output_ok and supply is not None and mode in ("HEAT", "COOL"):
                requested = delivered_target if delivered_target is not None else self.diagnostics.get("supply_target", fixed_target)
                self._supply_history.append((now, supply, requested, return_temperature))
            elif running:
                self._supply_history.clear()
            while self._supply_history and self._supply_history[0][0] < now - c["fault_seconds"]:
                self._supply_history.popleft()

        trends = {key: self._metrics(rows, now, c["trend_seconds"]) for key, rows in self._history.items()}
        if sampled and controlled and monitoring_ok and mode == "HEAT":
            for key, zone in eligible.items():
                metric = self._metrics(self._history[key], now, c["fault_seconds"])
                active = metric and metric["active_fraction"] >= c["minimum_active_fraction"]
                bad = bool(active and metric["mean_deficit"] >= c["boost_deficit"]
                           and metric["deficit"] >= c["boost_deficit"] and metric["rate"] < c["minimum_recovery_rate"])
                trend = trends.get(key)
                recovered = bool(monitoring_ok and running and trend and (
                    zone["deficit"] <= c["comfort_tolerance"] or trend["rate"] >= c["minimum_recovery_rate"]))
                self._fault(now, f"zone:{key}:insufficient_response", bad, recovered)
        if sampled:
            rows = self._supply_history
            observed = (len(rows) >= max(3, c["fault_seconds"] * c["minimum_active_fraction"] / c["sample_seconds"])
                        and rows[-1][0] - rows[0][0] >= c["fault_seconds"] * 0.9)
            error = abs(sum(row[1] - row[2] for row in rows) / len(rows)) if observed else None
            dt_rows = [row[1] - row[3] for row in rows if row[3] is not None]
            large_dt = mode == "HEAT" and observed and len(dt_rows) == len(rows) and sum(dt_rows) / len(dt_rows) > c["delta_t_alert"]
            self._fault(now, "supply_tracking", running and controlled and output_ok and error is not None and error > c["supply_tolerance"],
                        running and output_ok and supply is not None and abs(supply - (
                            delivered_target if delivered_target is not None else self.diagnostics.get("supply_target", fixed_target)
                        )) <= c["supply_tolerance"])
            self._fault(now, "large_delta_t", running and controlled and output_ok and large_dt,
                        running and output_ok and supply is not None and return_temperature is not None
                        and supply - return_temperature <= c["delta_t_alert"])

        reason = None
        if mode != "HEAT":
            reason = "inactive_mode"
        elif not weather:
            reason = "constant_strategy"
        elif fallback:
            reason = "outdoor_unavailable"
        elif outside:
            reason = "outside_curve_interval"
        elif not controlled:
            reason = "no_source_control"
        elif not output_ok:
            reason = "command_error"
        elif self._faults:
            reason = "suspected_fault"
        elif fallback_active:
            reason = "instance_temperature_fallback"
        elif not valid_zones:
            reason = "zone_data_unavailable"
        elif not running:
            reason = "source_not_running"

        desired_boost, limiting_zone = 0.0, None
        if weather and not fallback and controlled and output_ok and not self._faults and running:
            for key, zone in eligible.items():
                metric = trends.get(key)
                if not metric or metric["active_fraction"] < c["minimum_active_fraction"]:
                    continue
                if zone["deficit"] >= c["boost_deficit"]:
                    recovery_scale = max(0.0, min(1.0, 1 - metric["rate"] / c["minimum_recovery_rate"]))
                    requested = min(c["boost_max"], zone["deficit"] * c["boost_gain"] * recovery_scale)
                    if requested > desired_boost:
                        desired_boost, limiting_zone = requested, key
        elif weather and not fallback and controlled and output_ok and not self._faults and not running:
            # A normal OFF slot is not evidence that recovery is complete.
            if any(zone["deficit"] > c["comfort_tolerance"] for zone in eligible.values()):
                desired_boost = self.boost
        if not c["boost_enabled"] or not weather or fallback or not controlled or mode != "HEAT":
            self.boost = 0.0
        elif sampled:
            # A command failure or suspected fault permits withdrawal, never escalation.
            if not output_ok or self._faults:
                desired_boost = min(desired_boost, self.boost)
            change = c["boost_rate_per_hour"] * elapsed / 3600
            self.boost += max(-change, min(change, desired_boost - self.boost))

        boost_active = self.boost > 0.01 or desired_boost > 0.01
        if reason is None and boost_active:
            reason = "recovery_boost"
        if reason is None and c["learning_mode"] != "learn":
            reason = "learning_" + c["learning_mode"]
        learning_valid = False
        if reason == "source_not_running":
            # Normal OFF slots pause a trial; wall-clock idle time is not evidence.
            pass
        elif reason is not None:
            self.cancel_probe(now, reason)
        elif sampled:
            # Trials cannot use periods before enough actual activation was observed.
            metrics_valid = all(trends.get(key) and trends[key]["active_fraction"] >= c["minimum_active_fraction"] for key in eligible)
            if not metrics_valid:
                # Too little recent activation pauses observation; normal cycling
                # must not erase valid exposure accumulated in earlier cycles.
                reason = "insufficient_activation_history"
            else:
                learning_valid = True
                valid_elapsed = elapsed if self._previous_learning_valid else 0.0
                if valid_elapsed:
                    self.experience[point] += valid_elapsed
                    self._learning_elapsed[point] += valid_elapsed
                    self.revision += 1
                deficits = {key: zone["deficit"] for key, zone in eligible.items()}
                worst = max(deficits.values())
                if self.probe:
                    probe = self.probe
                    probe["observed_seconds"] += valid_elapsed
                    deteriorated = probe["direction"] < 0 and any(
                        trends[key]["mean_deficit"] > max(c["comfort_tolerance"], probe["deficits"][key] + c["comfort_tolerance"])
                        for key in deficits)
                    if not deteriorated:
                        probe.pop("bad_since", None)
                    else:
                        probe.setdefault("bad_since", now)
                    if abs(outdoor - probe["outdoor"]) > c["probe_outdoor_tolerance"]:
                        self.cancel_probe(now, "outdoor_changed")
                    elif deteriorated and now - probe["bad_since"] >= c["comfort_persistence_seconds"]:
                        self.probe = None
                        self._learning_elapsed[point] = 0.0
                        self._event(now, "probe_rejected", point=point, reason="comfort_deterioration")
                    elif probe["observed_seconds"] >= c["probe_seconds"]:
                        mean_worst = max(trends[key]["mean_deficit"] for key in deficits)
                        success = (worst <= c["comfort_tolerance"] and mean_worst <= c["comfort_tolerance"]) if probe["direction"] < 0 else (
                            mean_worst <= c["comfort_tolerance"] or
                            mean_worst <= probe["worst"] - c["minimum_learning_improvement"])
                        if success:
                            self.corrections[point] = probe["value"] - c["supply_points"][point]
                        self.probe = None
                        self._learning_elapsed[point] = 0.0
                        self._event(now, "probe_accepted" if success else "probe_rejected", point=point)
                elif self._learning_elapsed[point] >= c["learning_seconds"]:
                    direction = -1 if worst <= c["comfort_tolerance"] else 1
                    value = self._trial_value(point, direction)
                    current = c["supply_points"][point] + self.corrections[point]
                    if abs(value - current) >= 0.01:
                        self.probe = {"point": point, "value": value, "started": now,
                                      "direction": direction, "deficits": deficits,
                                      "worst": worst, "outdoor": outdoor, "observed_seconds": 0.0,
                                      "limited": abs(value - current - direction * c["learning_step"]) > 0.001}
                        self._learning_elapsed[point] = 0.0
                        self._event(now, "probe_started", point=point, direction=direction, value=value)
                    else:
                        reason = "curve_constraint"

        if sampled:
            self._previous_learning_valid = learning_valid

        corrected = list(c["supply_points"])
        if c["learning_mode"] != "off":
            corrected = [a + b for a, b in zip(corrected, self.corrections)]
        validated_target = interpolate(xs, corrected, outdoor) if weather and not fallback else fixed_target
        if self.probe:
            corrected[self.probe["point"]] = self.probe["value"]
        base = interpolate(xs, c["supply_points"], outdoor) if weather and not fallback else fixed_target
        learned_target = interpolate(xs, corrected, outdoor) if weather and not fallback else fixed_target
        raw = learned_target + self.boost
        prefix = "cooling" if mode == "COOL" else "heating"
        target = max(c[prefix + "_min"], min(c[prefix + "_max"], raw)) if mode != "OFF" else None
        limiting = min(eligible, key=lambda key: -eligible[key]["deficit"]) if eligible else None
        self.diagnostics = {
            "supply_strategy": "fallback_constant" if fallback else ("weather_compensated" if weather else "constant"),
            "supply_target": round(target, 2) if target is not None else None,
            "supply_curve_target": round(base, 2),
            "supply_learned_correction": round(validated_target - base, 2),
            "supply_probe_adjustment": round(learned_target - validated_target, 2),
            "supply_boost": round(self.boost, 2), "supply_outdoor": outdoor,
            "supply_actual": supply, "supply_return": return_temperature,
            "supply_delta_t": round(supply - return_temperature, 2) if supply is not None and return_temperature is not None else None,
            "supply_limiting_zone": (limiting_zone or limiting) if weather and (
                boost_active or self.probe is not None or c["learning_mode"] == "learn") else None,
            "supply_learning_status": ("probe_paused" if reason == "source_not_running" else "probing") if self.probe else (reason or "observing"),
            "supply_faults": sorted(self._faults), "supply_target_limited": target is not None and abs(raw - target) > 0.001,
            "supply_outside_curve": bool(outside), "supply_probe": deepcopy(self.probe),
            "supply_points": [{"outdoor": x, "base": b, "correction": round(d, 3),
                               "experience_seconds": round(e)} for x, b, d, e in zip(xs, c["supply_points"], self.corrections, self.experience)],
            "supply_zone_trends": deepcopy(trends), "supply_events": list(self.events),
        }
        return dict(self.diagnostics)
