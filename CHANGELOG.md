# Changelog

User-relevant changes are recorded here. Documentation in each release tag
corresponds to that release; the guides on `main` describe the current source.

## Unreleased

### Added

- Shared Virtual Climate sidebar panel with instance selection, basic thermostat
  controls, read-only supply diagnostics, and administrator supply settings.
- Conditional weather-curve editor with a graph, review of learning resets and
  reload effects, and protection against overwriting newer configuration edits.
- Panel **Zone settings** editor for one zone at a time (sensors, actuator,
  supported modes, window contact, timings, floor limits), with the same review
  and conflict protection.
- Read-only **Saved configuration** in the panel's Diagnostics page.
- Direct pump-only circuits: with a circulation pump and no heating or cooling
  source configured, Virtual Climate now runs the pump on zone demand; the
  source must operate independently. The options flow shows a notice before
  saving such a configuration.

### Changed

- **Cooling safety:** a zone with a configured humidity sensor stops cooling
  (block reason `rh_unavailable`) while the sensor or derived dew point is
  unavailable. Zones without a humidity sensor are unchanged. See ADR 0006.

### Fixed

- Exposed circuit profile, capabilities, reported state, external entity
  availability, and request timing basis as Plant state sensor attributes.
- Panel and options-flow supply editors keep the 0–90 °C supply limits of
  configurations created before `supply_control`, matching runtime behavior,
  instead of silently applying the 20–45 °C defaults on save.

### Documentation

- Operation now explains humidity and dew-point protection: the humidity alert
  reduces cooling demand, the dew-point margin compares the floor (or room air
  without a floor sensor) with the dew point, and the humidity fault has no
  clearing hysteresis.

- Reorganized English guides around setup, operation, optional features, and reference.
- Clarified direct versus external circuit ownership and adaptive heating limitations.
- Corrected UI help for floor protections and zone-update reload behavior; fixed repository links.
- Removed installation-specific reports and procedures from the repository tree.
- Documented the meaning of each `capabilities` flag; `supply_verification`
  means the supply sensor is valid while operating, not that the target is verified.
- Established documentation maintenance and contribution rules.

