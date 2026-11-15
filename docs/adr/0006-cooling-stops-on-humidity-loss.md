---
status: accepted
---

# Cooling stops when configured humidity is lost

Humidity and dew-point protections only act on values that are available. When
a zone has a humidity sensor configured (`sensor_rh`) and that sensor stops
reporting, or no dew point can be derived from it, the protections silently
disappear while cooling could continue. Condensation on a cooled surface is
a physical risk that the user chose to guard against by configuring the sensor.

Therefore, in cooling, a zone whose configured humidity sensor or derived dew
point is unavailable requests no demand and reports the block reason
`rh_unavailable`. The block clears as soon as both values return. Heating is
unaffected.

Zones without a configured humidity sensor keep cooling without humidity
protection, as before. This avoids stopping existing installations that cool
without humidity measurement.

Allowing an individual zone to continue cooling after humidity loss, by an
explicit setting, is a possible future extension and is not implemented.
