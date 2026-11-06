---
status: accepted
---

# Delayed zone control and observational learning

Zone heating policy can account for reported actuator history with explicit
delay and persistence. Use a bounded grid and constrained regression to identify
a simple thermal model, avoiding a machine-learning dependency or automatic
supply escalation. Delayed effect is an indicator, not measured energy.

Observational zone learning is separate from supply-curve learning. It can use
an independently managed source without inventing evidence of source operation.
This extends ADRs 0001–0003 only for the zone model; supply-curve learning retains
its controlled-request requirements.

Existing and new configurations default to `legacy`. `observe` learns from actual
commands without extra commands. `adaptive` is explicit and uses initial PI until
prediction eligibility is established by valid data, informative sequences, and
held-out improvement. Persist zone models separately from common supply learning;
rebuild active history and pulse balance after restart. Protections take priority.

Device firmware and local supply regulation remain outside the integration.
Commands use explicitly configured Home Assistant entities. Circuit ownership is
described in [Operation](../operation.md#circuit-responsibilities).

An accepted architectural decision does not mean comfort acceptance has passed.
The [feature guide](../features/adaptive-control.md) explains eligibility and
limitations; the [synthetic report](../development/observations/thermal-simulation-results.md)
preserves results, including unmet criteria.
