"""Delayed heating policy and observational identification, independent of HA.

Time is seconds, rates are degrees/hour. Effect is a dimensionless indicator,
never delivered energy. Only reported actuator activity enters the model.
"""
from collections import deque
from math import exp, isfinite

PROFILES = {
    "underfloor": dict(delay_minutes=45, persistence_minutes=180, trend_minutes=60,
                       horizon_minutes=360, integral_minutes=360),
    "radiator": dict(delay_minutes=20, persistence_minutes=45, trend_minutes=30,
                     horizon_minutes=180, integral_minutes=180),
}
STRATEGIES = ("legacy", "observe", "adaptive")
DEFAULTS = dict(comfort_below=0.2, comfort_above=0.3, deficit_weight=2.,
                variation_cost=0.02, start_cost=0.01, gain_per_hour=0.6,
                loss_per_hour=0.15, supply_reference=None)


def number(value):
    try:
        return float(value) if not isinstance(value, bool) and isfinite(float(value)) else None
    except (TypeError, ValueError, OverflowError):
        return None


def normalize(config=None, profile="underfloor"):
    if profile not in PROFILES:
        raise ValueError("Unknown thermal profile")
    if config is not None and not isinstance(config, dict):
        raise ValueError("thermal_parameters must be an object")
    if set(config or {}) - (DEFAULTS.keys() | PROFILES[profile].keys()):
        raise ValueError("Unknown thermal parameter")
    result = dict(DEFAULTS, **PROFILES[profile])
    result.update(config or {})
    for key, value in result.items():
        if key == "supply_reference" and value is None:
            continue
        value = number(value)
        if value is None or value < 0 or (key.endswith("minutes") and value <= 0):
            raise ValueError(f"Invalid thermal parameter: {key}")
        result[key] = value
    bounds = dict(delay_minutes=(1, 120), persistence_minutes=(5, 360),
                  trend_minutes=(5, 180), horizon_minutes=(30, 720), integral_minutes=(30, 1440),
                  gain_per_hour=(0.001, 10), loss_per_hour=(0, 5),
                  comfort_below=(0, 2), comfort_above=(0, 2), deficit_weight=(1, 10),
                  variation_cost=(0, 10), start_cost=(0, 10), supply_reference=(5, 90))
    for key, (low, high) in bounds.items():
        if result[key] is not None and not low <= result[key] <= high:
            raise ValueError(f"{key} outside [{low}, {high}]")
    return result


class ThermalZone:
    """A zone's transient memory, pulse balance and separately saved experience."""

    def __init__(self, profile="underfloor", parameters=None):
        self.profile = profile
        self.config = normalize(parameters, profile)
        self.parameters = {key: self.config[key] for key in (
            "delay_minutes", "persistence_minutes", "gain_per_hour", "loss_per_hour")}
        self.validated = False
        self.validation = {}
        self.valid_seconds = 0.
        self.sequences = 0
        self.samples = deque(maxlen=21 * 24 * 60)
        self.queue = deque()
        self.room_history = deque()
        self.effect = self.integral = self.balance = 0.
        self.last_time = self.last_target = self.warm_since = None
        self.previous_input = self.previous_demand = 0.
        self.previous_on = None
        self.previous_valid = False
        self.previous_stable = False
        self.learning_valid = False
        self.target_changed_at = None
        self.prediction = None
        self.reason = "initial"
        self.proposal = 0.
        self._last_fit = 0.
        self.accounted_at = None
        self.accounted_on = None
        self._heat_since = self._pause_since = None
        self._informative_heat = False

    def reset_transient(self):
        self.queue.clear()
        self.room_history.clear()
        self.effect = self.balance = 0.
        self.warm_since = None
        self.previous_valid = False
        self.learning_valid = False
        self._delayed = 0.

    @property
    def warm(self):
        return (self.warm_since is not None and self.last_time is not None and
                self.last_time - self.warm_since >= 60 * (self.parameters["delay_minutes"] +
                                                         3 * self.parameters["persistence_minutes"]))

    def update(self, now, air, target, on, proportional, *, blocked=False, supply=None,
               reference=None, availability=None, learn=True, stable=True, max_balance=1440,
               minimum_pulse=300, max_pulse=1440, minimum_off=0, restart_wait=0, on_for=0):
        """Sample real activity; no returned value commands hardware.

        availability=False requires independent evidence of unavailable heat. An
        absent source request or pump command is not such evidence.
        """
        self.minimum_off, self.restart_wait, self.on_for = minimum_off, restart_wait, on_for
        air, target = number(air), number(target)
        dt = 0 if self.last_time is None else now - self.last_time
        gap = dt < 0 or dt > 120
        if gap:
            self.reset_transient()
            dt = 0
        changed = self.last_target is not None and target != self.last_target
        if changed:
            self.target_changed_at = now
            self.balance = 0.
            if target is None or target < self.last_target:
                self.integral = 0.
        self.last_target = target
        valid = air is not None and target is not None and on is not None
        if blocked or not valid:
            self.balance = 0.
        self.account(now, on, max_balance)
        if blocked or not valid:
            self.balance = 0.
        ref = number(reference) if self.config["supply_reference"] is None else self.config["supply_reference"]
        weighted = air is not None and number(supply) is not None and ref is not None and ref > air
        activation = float(on is True)
        if weighted:
            activation *= max(0., min(2., (supply - air) / (ref - air)))
        if valid and self.previous_valid and dt:
            self.queue.append((now - dt, self.previous_input))
            delayed = getattr(self, "_delayed", 0.)
            cutoff = now - self.parameters["delay_minutes"] * 60
            while self.queue and self.queue[0][0] <= cutoff:
                delayed = self.queue.popleft()[1]
            # Retain the delayed input between irregular state callbacks.
            if cutoff >= (self.warm_since if self.warm_since is not None else now):
                self._delayed = delayed
                self.effect = self.effect * exp(-dt / (60 * self.parameters["persistence_minutes"])) + self._delayed * (1 - exp(-dt / (60 * self.parameters["persistence_minutes"])))
            if self.learning_valid and learn and not blocked:
                self.valid_seconds += dt
                if on is True:
                    if self.previous_on is not True or self._heat_since is None:
                        self._heat_since = now
                    self._pause_since = None
                elif self.previous_on is True:
                    self._informative_heat = self._heat_since is not None and now - self._heat_since >= minimum_pulse
                    self._pause_since = now
                elif self._informative_heat and self._pause_since is not None and now - self._pause_since >= minimum_pulse:
                    self.sequences += 1
                    self._informative_heat = False
        if valid:
            if self.warm_since is None:
                self.warm_since = now
            if self.learning_valid and not blocked and learn and (not self.samples or now - self.samples[-1][0] >= 60):
                # Segments break explicitly across excluded or missing intervals.
                self.samples.append((now, air, activation))
            self.room_history.append((now, air))
            while self.room_history and now - self.room_history[0][0] > self.config["trend_minutes"] * 60:
                self.room_history.popleft()
        else:
            self.reset_transient()
        error = (target - air) if valid else 0.
        correction = max(0., min(1., proportional))
        maintenance_stable = self.target_changed_at is None or now - self.target_changed_at >= self.config["trend_minutes"] * 60
        if valid and learn and not blocked and availability is not False and stable and maintenance_stable and not changed and dt:
            candidate = self.integral + error * dt / (1.5 * 60 * self.config["integral_minutes"])
            if not ((correction + self.integral >= 1 and error > 0) or (self.integral <= 0 and error < 0)):
                self.integral = max(0., min(1., candidate))
        self.proposal = max(0., min(1., correction + self.integral)) if valid and not blocked else 0.
        self.reason = "blocked" if blocked else "invalid_observation" if not valid else "initial_pi"
        self.last_time = now
        self.prediction = None
        if valid and not blocked and self.validated and self.warm:
            self.proposal = self.choose(air, target, minimum_pulse, max_pulse)
            self.reason = "validated_prediction"
        self.previous_input, self.previous_on = activation, on
        self.previous_valid = valid
        self.learning_valid = valid and not blocked and learn
        if not self.learning_valid:
            self._heat_since = self._pause_since = None
            self._informative_heat = False
        self.previous_demand = self.proposal
        self.previous_stable = stable
        self.weighted = weighted
        # Start only when accumulated credit justifies all unavoidable extensions.
        pulse = valid and not blocked and (self.balance >= minimum_pulse if on is not True else self.balance > 0)
        duration = min(max_pulse, max(minimum_pulse, self.balance)) if pulse else 0.
        return dict(proposal=self.proposal, pulse_on=pulse, pulse_seconds=duration)

    def account(self, now, on, limit):
        """Account every reported transition, independently of model sampling."""
        dt = 0 if self.accounted_at is None else now - self.accounted_at
        if 0 <= dt <= 120:
            self.balance = max(-limit, min(limit, self.balance + dt *
                (self.previous_demand - float(self.accounted_on is True))))
        else:
            self.balance = 0.
        self.accounted_at, self.accounted_on = now, on

    def forecast(self, air, demand, minimum_pulse, max_pulse):
        """Predict useful pulses, with already queued input and residual effect."""
        cfg, par = self.config, self.parameters
        delay = max(1, round(par["delay_minutes"]))
        pending = [value for _, value in self.queue][-delay:]
        pending = deque([0.] * (delay - len(pending)) + pending)
        effect, temperature, credit = self.effect, air, self.balance
        active = self.previous_on is True
        remaining = max(0., minimum_pulse - getattr(self, "on_for", 0)) / 60 if active else 0
        off_remaining = getattr(self, "restart_wait", 0) / 60
        minimum_off = getattr(self, "minimum_off", 0) / 60
        a = exp(-1 / par["persistence_minutes"])
        gain, loss = par["gain_per_hour"] / 60, par["loss_per_hour"] / 60
        predictions, starts = [], 0
        for _ in range(round(cfg["horizon_minutes"])):
            if remaining <= 0:
                if not active and off_remaining <= 0 and credit >= minimum_pulse:
                    active, remaining, starts = True, minimum_pulse / 60, starts + 1
                elif active and credit <= 0:
                    active = False
                    off_remaining = minimum_off
            credit = max(-max_pulse, min(max_pulse, credit + 60 * (demand - active)))
            remaining -= 1
            off_remaining -= 1
            pending.append(float(active))
            effect = a * effect + (1 - a) * pending.popleft()
            temperature += gain * effect - loss
            predictions.append(temperature)
        return predictions, starts

    def choose(self, air, target, minimum_pulse, max_pulse):
        best = None
        for demand in [self.previous_demand] + [i / 20 for i in range(21)]:
            predictions, starts = self.forecast(air, demand, minimum_pulse, max_pulse)
            lower, upper = target - self.config["comfort_below"], target + self.config["comfort_above"]
            weight = self.config["deficit_weight"]
            cost = sum(weight * (lower-t)**2 if t < lower else (t-upper)**2 if t > upper else 0.
                       for t in predictions) / 60
            cost += self.config["variation_cost"] * (demand - self.previous_demand) ** 2
            cost += self.config["start_cost"] * starts
            if best is None or cost < best[0] - 1e-10:
                best = cost, demand, predictions[-1]
        self.prediction = best[2]
        return best[1]

    @staticmethod
    def _rows(samples, delay, persistence):
        """One-minute rates; restart filter at gaps and exclude its warm-up."""
        rows, pending = [], deque()
        effect, warm = 0., 0
        for previous, sample in zip(samples, samples[1:]):
            dt = sample[0] - previous[0]
            if not 59 <= dt <= 61:
                pending.clear()
                effect, warm = 0., 0
                continue
            pending.append(previous[2])
            delayed = pending.popleft() if len(pending) > delay else 0.
            a = exp(-1 / persistence)
            effect = a * effect + (1 - a) * delayed
            warm += 1
            if warm >= delay + 3 * persistence:
                rows.append((sample[0], effect, (sample[1] - previous[1]) * 60))
        return rows

    def fit(self, now):
        """Bounded grid + nonnegative least squares, chronological held-out check."""
        if now - self._last_fit < 6 * 3600:
            return False
        self._last_fit = now
        if self.valid_seconds < 7 * 86400 or self.sequences < 3 or len(self.samples) < 7 * 1440:
            return False
        samples = list(self.samples)
        split = samples[int(len(samples) * .7)][0]
        best = None
        fits = []
        base = PROFILES[self.profile]
        for delay in sorted({max(1, round(base["delay_minutes"] * factor)) for factor in (.5, .75, 1, 1.5, 2)}):
            for persistence in sorted({max(5, min(360, round(base["persistence_minutes"] * factor))) for factor in (.5, .75, 1, 1.5, 2)}):
                rows = self._rows(samples, delay, persistence)
                train = [(x, y) for t, x, y in rows if t < split]
                if len(train) < 100:
                    continue
                n = len(train)
                sx, sy = sum(x for x, _ in train), sum(y for _, y in train)
                sxx, sxy = sum(x*x for x, _ in train), sum(x*y for x, y in train)
                variance = sxx - sx*sx/n
                if variance / n < .005:
                    continue  # Heating and loss cannot be identified separately.
                # Enumerate the unconstrained optimum and both boundary optima.
                gain = (sxy - sx*sy/n) / variance
                loss = (gain*sx - sy)/n
                candidates = [(max(.001, min(10., (sxy+fixed_loss*sx)/max(sxx, 1e-9))), fixed_loss)
                              for fixed_loss in (0., 5.)]
                candidates.extend((fixed_gain, max(0., min(5., (fixed_gain*sx-sy)/n)))
                                  for fixed_gain in (.001, 10.))
                if .001 <= gain <= 10 and 0 <= loss <= 5:
                    candidates.append((gain, loss))
                gain, loss = min(candidates, key=lambda p: sum((p[0]*x-p[1]-y)**2 for x,y in train))
                error = sum((gain*x-loss-y)**2 for x,y in train)/n
                fits.append(error)
                if best is None or error < best[0]:
                    best = error, delay, persistence, gain, loss, rows
        if best is None or (len(fits) > 1 and sorted(fits)[1] <= best[0] * 1.01 + 1e-12):
            self.validation = dict(reason="unidentifiable")
            return False
        _, delay, persistence, gain, loss, rows = best
        held = [(x,y) for t,x,y in rows if t >= split]
        baseline = [(x,y) for t,x,y in self._rows(samples, round(self.config["delay_minutes"]),
                    self.config["persistence_minutes"]) if t >= split]
        if len(held) < 1440 or len(baseline) < 1440:
            return False
        error = sum((gain*x-loss-y)**2 for x,y in held)/len(held)
        initial = sum((self.config["gain_per_hour"]*x-self.config["loss_per_hour"]-y)**2 for x,y in baseline)/len(baseline)
        improvement = 1-error/initial if initial > 1e-12 else 0.
        self.validation = dict(held_out_mse=error, initial_mse=initial, improvement=improvement,
                               held_out_samples=len(held), reason="accepted" if improvement >= .15 else "insufficient_improvement")
        if improvement < .15:
            return False
        self.parameters = dict(delay_minutes=delay, persistence_minutes=persistence,
                               gain_per_hour=gain, loss_per_hour=loss)
        self.validated = True
        self.reset_transient()
        return True

    def diagnostics(self):
        return dict(profile=self.profile, parameters=self.parameters.copy(), maintenance_demand=self.integral,
                    comfort_correction=max(0., self.proposal-self.integral), delayed_effect=self.effect,
                    predicted_temperature=self.prediction, confidence=("validated" if getattr(self, "weighted", False) else "validated_unweighted") if self.validated and self.warm else "initial",
                    room_trend_per_hour=((self.room_history[-1][1]-self.room_history[0][1])*3600 / (self.room_history[-1][0]-self.room_history[0][0])) if len(self.room_history)>1 and self.room_history[-1][0]>self.room_history[0][0] else None,
                    supply_weighted=getattr(self, "weighted", False), history_ready=self.warm,
                    pulse_balance_seconds=self.balance, proposed_fraction=self.proposal,
                    reason=self.reason, valid_seconds=self.valid_seconds, informative_sequences=self.sequences,
                    validation=self.validation.copy())

    def snapshot(self):
        return dict(profile=self.profile, config=self.config.copy(), parameters=self.parameters.copy(),
                    validated=self.validated, validation=self.validation.copy(), valid_seconds=self.valid_seconds,
                    sequences=self.sequences, samples=list(self.samples), integral=self.integral, last_target=self.last_target)

    def restore(self, data):
        if not isinstance(data, dict) or data.get("profile") != self.profile or data.get("config") != self.config:
            return
        parameters = normalize(data.get("parameters"), self.profile)
        # Validate persisted data before committing any of it to the instance.
        samples = data.get("samples", [])
        if not isinstance(samples, list) or any(len(s) != 3 or any(number(v) is None for v in s) for s in samples):
            raise ValueError("Invalid thermal observations")
        self.parameters = {key: parameters[key] for key in self.parameters}
        self.validated = data.get("validated") is True
        self.validation = dict(data.get("validation", {}))
        self.valid_seconds = max(0., number(data.get("valid_seconds")) or 0.)
        self.sequences = max(0, int(data.get("sequences", 0)))
        self.samples.extend(tuple(s) for s in samples[-self.samples.maxlen:])
        self.integral = max(0., min(1., number(data.get("integral")) or 0.))
        self.last_target = number(data.get("last_target"))
        self.reset_transient()
