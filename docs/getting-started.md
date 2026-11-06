# Getting started

Virtual Climate works with entities already exposed in Home Assistant. It creates
thermostats and coordinates commands; it does not discover or configure hardware.

## Prepare the entities

For each zone, identify:

- An air temperature sensor and a relative humidity sensor.
- A switch or compatible group controlling the zone actuator.
- Optional floor temperature and window contact sensors.
- The actuator opening and closing times supplied for your equipment.

Create an **Input select** helper with `HEAT`, `COOL`, and `OFF` options for the
global operating mode. Select `OFF` while configuring. A heating-only setup can
use `HEAT` and `OFF`; select heating-only support for its zones.

Decide who controls the shared circuit:

| Profile | Pump and source sequencing | Required circuit command |
| --- | --- | --- |
| `direct` | Virtual Climate for configured outputs | Configure the pump/source switches that it should own; omitted outputs remain independent |
| `external` | A separate controller | A `switch` or `input_boolean` accepting heating demand |

Read [Operation](operation.md) for the responsibility boundary. A local device
regulates supply temperature and provides equipment protections. Configure only
outputs that this integration is intended to control.

## Install

### HACS

1. Open HACS and add `https://github.com/alexelite/ha-virtual-climate` as a custom
   repository, category **Integration**.
2. Install **Virtual Climate**.
3. Restart Home Assistant.

### Manual installation

1. Download the repository version you want to install.
2. Copy `custom_components/virtual_climate` into the `custom_components` directory
   in your Home Assistant configuration.
3. Restart Home Assistant.

## Configure the first zone

1. Open **Settings → Devices & services → Add integration** and select
   **Virtual Climate**.
2. Choose manual configuration and select your global mode helper.
3. Select the circuit profile and its command entities. For `external`, clear
   direct pump, source, and changeover fields; see [External circuit](features/external-circuit.md).
4. Set actuator and circuit timings to match your equipment. The supplied
   defaults are starting values, not equipment specifications.
5. Add a zone using the wizard. Give it a unique ID and select its sensors,
   actuator, supported modes, and optional floor/window sensors.
6. If the integration should transmit a supply target, configure
   **Supply temperature control**. Start with a constant target appropriate for
   the equipment. Keep the default `legacy` heating strategy.
7. Finish setup and add the new climate entity to your dashboard.

## Check the first cycle

Set the global helper to `HEAT`, set the zone to `AUTO`, and choose a room
setpoint above the measured room temperature. Check the actuator state and
[diagnostics](reference/diagnostics.md). Opening time, restart lockout, and
scheduled offsets can delay a source request.

Verify that configured pump/source commands follow the intended sequence, or
that external demand reaches the controller. Compare software reports with your
equipment's actual behavior; switch `on` alone does not establish water flow.

Use [Troubleshooting](troubleshooting.md) if demand exists but heating does not
start. Add other zones after checking the first one. Optional learning and
adaptive control are separate configuration choices.
