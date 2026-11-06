# Virtual Climate

Multi-zone hydronic heating and cooling with a shared circuit supply temperature.

## Language

**Configuration entry**:
An independently configured set of zones and their shared circuit in Home Assistant.

**Zone**:
A room or heating area with its own setpoint, measurements, and actuator.

**Circuit**:
The shared hydronic path serving a configuration entry's zones.

**Operating request**:
A command requesting circuit or source operation. It does not establish actual
water flow, combustion, or heat delivery.

**Local supply regulation**:
The device's regulation of actual supply temperature around a requested target.

**Room setpoint**:
The desired room air temperature, distinct from water temperature.

**Target supply temperature**:
The desired water temperature supplied to the circuit.

**Actual supply temperature**:
The measured water temperature supplied to the circuit.

**Temperature fallback**:
An estimated room-temperature reference from measured rooms in the same entry,
used temporarily when a zone lacks its own measurement.

**Opportunistic heating**:
Heating a zone only while other zones request circuit operation, without that
zone creating its own source request.

**Weather compensation**:
Adjustment of target supply temperature according to outdoor conditions and,
when enabled, observed indoor response.

**Base weather curve**:
The reference relationship between outdoor temperature and target supply before
learned or temporary corrections.

**Recovery boost**:
A temporary increase in target supply associated with room deficit. Deficit
alone does not establish a fault or justify repeated target increases.

**Learned correction**:
An adjustment inferred from observed thermal response, distinct from recovery
boost. It can differ across outdoor conditions.

**Curve point**:
An outdoor reference temperature and associated supply temperature. Its base
value and learned correction are distinct.

**Point learning interval**:
The outdoor range bounded by midpoints to neighboring points, used to attribute
observations. It does not bound the point's influence on interpolation.

**Supply strategy**:
The method of selecting target supply temperature: constant temperature or
weather compensation, selected separately for heating and cooling.

**Constant fallback target**:
The explicitly configured supply target used when outdoor data required for
weather compensation is invalid.

**Delayed thermal effect**:
An indicator of thermal influence that follows actuator activation after a
delay and persists after closure. It is not measured energy.

**Maintenance demand**:
The heating-time fraction needed to offset a zone's losses near its room setpoint.

**Pulse balance**:
The bounded difference between requested activation time and reported actual
activation time, including circulation extensions.

**Observational zone learning**:
Estimation of room thermal response from its own measurements and reported
actuator activity, including with an independently managed source.
