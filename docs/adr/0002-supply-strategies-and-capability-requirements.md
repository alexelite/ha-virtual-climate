---
status: accepted
---

# Per-mode supply strategies and feature-specific requirements

Supply strategy is selected separately for heating and cooling. Having outdoor
sensors does not force weather compensation. Constant targets remain valid
choices; heating weather compensation needs valid outdoor data. Cooling uses a
constant target.

Each feature has its own data/control requirements. Missing an optional sensor
must disable only features that require it, rather than invalidating the entire
integration.

| Feature | Required information/context |
| --- | --- |
| Constant target calculation | Configured target for the active mode |
| Weather-curve calculation | Valid outdoor temperature, curve, and supply limits |
| Target transmission | Available writable target entity and successful command |
| Recovery boost | Active weather compensation, eligible room deficits/trends and reported activation, controlled request context |
| Curve learning | Valid eligible room/activity observations, outdoor conditions inside the configured interval, controlled request context, and valid trials |
| Room-response monitoring | Eligible room measurements/activity and controlled request context |
| Supply target verification | Valid supply sensor, transmitted target, and operating context |
| Supply-return difference | Both supply and return sensors; fault interpretation also needs operating context |

Reported activation does not establish delivered heat. Flow-based power and
energy measurement are outside these capabilities.

When outdoor data becomes invalid, weather compensation uses the explicitly
configured constant heating fallback. Learning and boost pause so the fallback
remains constant. Other monitoring can continue when its requirements are met.
Recovery of valid outdoor data resumes curve calculation; learning waits for
fresh observations.

See [Supply control](../features/supply-control.md) and the
[external profile](../features/external-circuit.md) for current profile-specific
requirements. Direct startup with weather compensation requires target output;
external demand can operate with the device's own target.
