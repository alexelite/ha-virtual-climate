---
status: accepted
---

# Separate supply target calculation from local regulation

Virtual Climate calculates a target supply temperature and transmits it through
a configured entity. A local device regulates the actual water temperature and
implements equipment-specific protections. This separates room/weather policy
from device-dependent regulation and avoids implementing mixing-valve control
in Home Assistant.

Slow radiant systems need response evaluation over meaningful periods rather
than strict instantaneous tracking. Persistent deviations can justify diagnostic
notifications without establishing their physical cause or automatically stopping
heating. Existing protection limits retain priority.

Supply-curve learning and active response monitoring use context from operating
requests controlled by Virtual Climate. Curve calculation alone does not justify
learning. Suspected faults suspend learning for the common curve so a faulty
zone is not silently excluded from comfort evaluation; validated corrections
remain available. Recovery requires sustained acceptable response and does not
override explicitly frozen learning.

A command failure is distinct from a thermal-response fault. A required startup
target write must succeed before a source request. An operational write failure
causes controlled retries and notification without itself stopping the source.
Write success does not confirm achieved supply temperature.

The [supply guide](../features/supply-control.md) and
[reference](../reference/configuration.md#supply-policy) define current behavior
and configurable thresholds. [Operation](../operation.md#circuit-responsibilities)
distinguishes direct and external sequencing ownership; both retain local
supply regulation in the device.
