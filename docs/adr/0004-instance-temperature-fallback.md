---
status: accepted
---

# Opportunistic heating with an entry-level fallback temperature

A zone without its own room measurement can use the median of real measurements
in the same entry to calculate actuator demand while its displayed measured
temperature remains unavailable. Only measured zones request the source and
determine the cycle; fallback zones join their operating windows. This preserves
a useful setpoint without presenting an estimate as an observation.

The feature is opt-in and heating-only. Fallback zones do not contribute to
recovery boost or room-response monitoring. Active fallback suspends learning of
the common supply curve under the conservative policy in ADRs 0001–0003, retaining
validated corrections. Measured rooms may still determine boost. Without valid
measured demand, fallback cannot start the circuit.

See [Temperature fallback](../features/temperature-fallback.md) for behavior and
limitations, including the risk of an estimate overheating or underheating a room.
