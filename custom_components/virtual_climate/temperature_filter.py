"""Time-based room-temperature smoothing, independent of sensor message counts."""
from __future__ import annotations

import math


class TemperatureFilter:
    """EMA sampled by the control clock, never by incoming sensor packets."""

    def __init__(self, time_constant_s: float = 180.0, sample_interval_s: float = 60.0,
                 reset_gap_s: float = 300.0):
        self.time_constant_s = time_constant_s
        self.sample_interval_s = sample_interval_s
        self.reset_gap_s = reset_gap_s
        self._value = None
        self._sampled_at = None
        self._source = None
        self._enabled = None

    def update(self, value: float | None, now: float, *, source: str | None,
               enabled: bool = True, control_sample: bool = False) -> float | None:
        """Use elapsed monotonic seconds; invalid readings immediately clear memory."""
        if value is None or not math.isfinite(value):
            self._value = self._sampled_at = None
            return None
        reset = (self._value is None or self._sampled_at is None
                 or source != self._source or enabled != self._enabled)
        elapsed = 0.0 if self._sampled_at is None else now - self._sampled_at
        reset = reset or elapsed < 0 or elapsed > self.reset_gap_s
        self._source, self._enabled = source, enabled
        if reset or not enabled:
            self._value, self._sampled_at = value, now
        elif control_sample or elapsed >= self.sample_interval_s:
            alpha = -math.expm1(-elapsed / self.time_constant_s)
            self._value += alpha * (value - self._value)
            self._sampled_at = now
        return self._value
