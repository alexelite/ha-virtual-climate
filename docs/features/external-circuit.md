# External circuit control

Use `external` when a separate controller owns the pump, mixing valve, and
source sequence. Virtual Climate schedules zone actuators and sends heating
demand. The integration communicates through configured Home Assistant entities
and does not require a particular controller or firmware platform.

External control supports heating only. Cooling remains available through a
suitable direct-profile configuration. Existing entries default to `direct`;
profile changes are explicit.

## Configure

In **Global Settings**, select `external`, set **External circuit demand** to a
`switch` or `input_boolean`, and optionally choose a reported circuit-state
sensor. Clear direct pump, heating source, cooling source, and changeover fields.
Validation rejects configurations that assign both owners.

This is a fragment of the `global` object, not a complete import:

```json
{
  "circuit_control": "external",
  "circuit_demand_entity": "switch.circuit_demand",
  "circuit_state_entity": "sensor.circuit_state",
  "circulation_pump_entity": null,
  "heating_source_entity": null,
  "cooling_source_entity": null,
  "changeover_entity": null,
  "external_start_delay_seconds": 0,
  "external_post_run_seconds": 120
}
```

A target supply entity is optional. Without one, demand can start and the
controller can use its own local target. If one is configured, Virtual Climate
writes it before demand and handles errors. Weather-curve calculation remains
independent of target transmission; monitoring target achievement requires an
actually transmitted target and a supply sensor.

## Timing and circulation paths

Before demand starts, Virtual Climate waits for the greater of zone opening
readiness and its external startup delay, writes a configured target, and
rechecks demand. Direct pump/source delay settings do not participate.
Minimum run time starts when demand is activated. Minimum off time starts when
demand is withdrawn, independently of when zone valves close.

After withdrawing demand, Virtual Climate holds valid circulation paths open for
`external_post_run_seconds`. **This hold must be at least as long as the external
controller's post-run.** Increase the integration's hold before increasing the
controller's post-run. Reported circuit state does not shorten the timer.

A new request cancels scheduled closure but still respects normal restart rules.
Safety-blocked zones are never held open as valid paths. Unloading the integration
withdraws demand and waits for the hold before closing zones; an abrupt Home
Assistant process stop cannot execute that sequence.

## Changing ownership

Export the current configuration. Stop demand and let circulation finish before
changing ownership. Remove competing pump/source commands and configure exactly
one owner for each output. Check the controller's own protections, demand
semantics, and startup/post-run times before activating the new profile.

After changing the profile, verify zone opening, demand, target transmission if
used, and shutdown hold across several cycles. Reverting ownership also requires
withdrawing demand and allowing post-run to finish before restoring direct
outputs.

## Connection loss

Virtual Climate implements no demand expiry or watchdog. The external device's
behavior on API loss, Home Assistant failure, and device restart is defined by
that device. A last asserted demand may remain active. Verify this policy with
the controller rather than assuming Home Assistant shutdown timing will run.

The optional reported state is diagnostic feedback, not proof of source operation
or a replacement for timing alignment. See [Operation](../operation.md#protection-and-reported-state).
