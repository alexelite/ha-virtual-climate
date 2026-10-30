#pragma once
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <deque>

namespace virtual_climate {
inline double uptime_seconds(uint32_t milliseconds) {
  static uint32_t previous = 0;
  static uint64_t wraps = 0;
  if (milliseconds < previous) wraps += uint64_t(1) << 32;
  previous = milliseconds;
  return double(wraps + milliseconds) / 1000.;
}
inline bool heat_relay(bool underfloor, bool radiator, bool cooling) {
  return !cooling && (underfloor || radiator);
}
enum class ValveState { idle_closed, prepositioning, settling, regulating, manual, fault, calibrating };
inline const char *state_name(ValveState state) {
  switch (state) {
    case ValveState::idle_closed: return "idle_closed";
    case ValveState::prepositioning: return "prepositioning";
    case ValveState::settling: return "settling";
    case ValveState::regulating: return "regulating";
    case ValveState::manual: return "manual";
    case ValveState::fault: return "fault";
    default: return "calibrating";
  }
}
struct MixingConfig {
  float absolute_max;  // No safe universal default: required at integration.
  float band = 2, large_error = 5, small_step = .01f, large_step = .02f;
  float trend_per_minute = .2f, initial_position = .10f, return_per_minute = .30f;
  float remember_target_delta = 1, trip_delta = 8, recovery_delta = 2;
  uint32_t sample_window = 120, move_pause = 90, settling = 120;
  uint32_t remember_after = 300, remember_quiet = 120, remember_pause = 1800;
  uint32_t trip_hold = 15, invalid_hold = 30, recovery_hold = 120, evaluate = 30;
};
struct ValveInput {
  double now;
  float raw, filtered, target, position;
  bool pump, heating, cooling, manual, calibrated, moving, exercising;
};
struct ValveOutput {
  bool command = false;
  float position = 0;
};
class MixingController {
 public:
  explicit MixingController(MixingConfig config) : config(config) {}
  MixingConfig config;
  ValveState state = ValveState::calibrating;
  bool remembered = false;
  float remembered_position = 0, remembered_target = 0;
  double remembered_at = 0;
  float average = NAN, trend = NAN;

  void motion_finished(double now) { last_motion_end_ = now; }
  // Call only for a fresh NTC reading, including invalid readings. The raw
  // value bypasses smoothing for safety. Pump-off values never enter control.
  void sample(const ValveInput &in) {
    if (std::isfinite(in.raw) && in.raw > -20 && in.raw < 120) {
      raw_ = in.raw;
      last_valid_ = in.now;
    }
    if (in.pump && in.heating && std::isfinite(in.raw)) {
      median_.push_back(in.raw);
      if (median_.size() > 3) median_.pop_front();
      auto sorted = median_;
      std::sort(sorted.begin(), sorted.end());
      float median = sorted[sorted.size()/2];
      if (!std::isfinite(ema_)) ema_ = median;
      else ema_ += (median - ema_) * (1 - std::exp(-(in.now - last_sample_) / 30));
      last_sample_ = in.now;
      samples_.emplace_back(in.now, ema_);
      while (!samples_.empty() && in.now - samples_.front().first > config.sample_window)
        samples_.pop_front();
    } else if (!in.pump || !in.heating) {
      // Restart the circulation-only filter; pause temperatures never leak into
      // the decision window through an EMA or median retained across the pause.
      median_.clear();
      ema_ = NAN;
      samples_.clear();
    }
  }

  ValveOutput tick(const ValveInput &in) {
    ValveOutput out;
    auto move = [&](float position) {
      out.command = true;
      out.position = std::max(0.f, std::min(1.f, position));
      if (std::fabs(out.position - in.position) > .0001f) last_correction_ = last_motion_end_ = in.now;
    };
    const bool valid = std::isfinite(raw_) && last_valid_ >= 0 &&
                       in.now - last_valid_ < config.invalid_hold;
    const bool target_valid = std::isfinite(in.target);
    if (!in.heating || in.manual || !in.calibrated) remembered = false;
    if (!in.calibrated) {
      state = ValveState::calibrating;
      remembered = false;
      return out;  // Boot homing owns the actuator, independently of regulation.
    }
    if (in.moving) last_motion_end_ = in.now;
    const float trip = target_valid ? std::min(config.absolute_max, in.target + config.trip_delta) : config.absolute_max;
    if (valid && in.heating && target_valid && raw_ >= in.target + config.trip_delta) {
      if (over_since_ < 0) over_since_ = in.now;
    } else over_since_ = -1;
    if (!valid || !target_valid || !std::isfinite(config.absolute_max) || config.absolute_max <= 0 ||
        (valid && raw_ >= config.absolute_max) ||
        (over_since_ >= 0 && in.now - over_since_ >= config.trip_hold)) {
      state = ValveState::fault;
      remembered = false;
      recovery_since_ = -1;
    }
    if (state == ValveState::fault) {
      move(0);  // Close hot contribution, leave the pump command to its owner.
      if (valid && target_valid && raw_ <= trip - config.recovery_delta) {
        if (recovery_since_ < 0) recovery_since_ = in.now;
        if (in.now - recovery_since_ >= config.recovery_hold) {
          state = ValveState::idle_closed;
          was_pump_ = false;
          recovery_since_ = -1;
        }
      } else recovery_since_ = -1;
      return out;
    }
    if (!in.pump) {
      if (was_pump_) stopped_at_ = in.now;
      was_pump_ = false;
      state = ValveState::idle_closed;
      samples_.clear();
      average = trend = NAN;
      if (!in.exercising) move(0);
      return out;
    }
    if (in.exercising) return out;  // Exclusive exercise ownership.
    if (in.manual || in.cooling || !in.heating) {
      state = ValveState::manual;
      was_pump_ = false;
      samples_.clear();
      return out;  // Cooling keeps its existing local policy in the adapter.
    }
    if (!was_pump_) {
      const bool reuse = remembered && in.now - stopped_at_ <= config.remember_pause &&
                         std::fabs(in.target - remembered_target) <= config.remember_target_delta;
      preposition_ = reuse ? remembered_position : config.initial_position;
      if (!reuse) remembered = false;
      state = ValveState::prepositioning;
      circulation_since_ = last_step_ = in.now;
      was_pump_ = true;
    }
    // Any fresh excursion above the control band interrupts the warm return.
    if (state == ValveState::prepositioning && valid && raw_ > in.target + config.band) {
      move(0);
      state = ValveState::settling;
      settled_since_ = in.now;
      return out;
    }
    if (state == ValveState::prepositioning) {
      float step = config.return_per_minute * float(in.now - last_step_) / 60;
      last_step_ = in.now;
      if (!in.moving) {
        if (std::fabs(in.position - preposition_) < .005f) {
          state = ValveState::settling;
          settled_since_ = in.now;
        } else move(in.position + std::max(-step, std::min(step, preposition_ - in.position)));
      }
      return out;
    }
    if (samples_.size() < 2) return out;
    average = 0;
    for (auto &sample : samples_) average += sample.second;
    average /= samples_.size();
    double span = samples_.back().first - samples_.front().first;
    trend = span > 0 ? (samples_.back().second - samples_.front().second) * 60 / span : 0;
    if (state == ValveState::settling) {
      if (in.moving) settled_since_ = in.now;
      if (in.now - settled_since_ < config.settling || span < config.sample_window - 5) return out;
      state = ValveState::regulating;
    }
    if (in.now - circulation_since_ >= config.remember_after &&
        std::fabs(average - in.target) <= config.band && !in.moving &&
        in.now - last_correction_ >= config.remember_quiet) {
      remembered = true;
      remembered_position = in.position;
      remembered_target = in.target;
      remembered_at = in.now;
    }
    if (in.now - last_evaluate_ < config.evaluate) return out;
    last_evaluate_ = in.now;
    float error = in.target - average;
    int direction = error > config.band ? 1 : error < -config.band ? -1 : 0;
    // Persistence requires two decisions outside the band in the same direction.
    bool persistent = direction && direction == previous_direction_;
    previous_direction_ = direction;
    if (!persistent || in.moving || in.now - last_motion_end_ < config.move_pause) return out;
    if ((direction > 0 && trend >= config.trend_per_minute) ||
        (direction < 0 && trend <= -config.trend_per_minute)) return out;
    move(in.position + direction * (std::fabs(error) > config.large_error ? config.large_step : config.small_step));
    return out;
  }
 private:
  std::deque<std::pair<double, float>> samples_;
  std::deque<float> median_;
  float ema_ = NAN;
  double last_sample_ = 0;
  float raw_ = NAN, preposition_ = 0;
  bool was_pump_ = false;
  int previous_direction_ = 0;
  double last_valid_ = -1, over_since_ = -1, recovery_since_ = -1;
  double stopped_at_ = -1e9, circulation_since_ = 0, settled_since_ = 0;
  double last_correction_ = 0, last_motion_end_ = 0, last_evaluate_ = 0, last_step_ = 0;
};
}  // namespace virtual_climate
