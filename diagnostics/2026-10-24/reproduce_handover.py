"""Offline probe of the live handover/no_flow pattern. Never connects to HA.

Run: python3 diagnostics/2026-10-24/reproduce_handover.py
Exit 1 means a planned handover closed the old path before confirmation of
the replacement and interrupted a source that had run for only 30 seconds.
"""
import asyncio
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tests"))
from support import coordinator, zone


async def probe(delayed_feedback):
    manager, hass, clock = coordinator({
        "heating_source_entity": "switch.source",
        "circulation_pump_entity": "switch.pump",
        "heating_source_start_delay_seconds": 30,
        "pump_start_delay_seconds": 0,
        "minimum_off_time_seconds": 180,
        "minimum_run_time_seconds": 300,
        "pump_post_run_seconds": 120,
    }, [zone("old", delta=0.1), zone("new", delta=0.7)])
    # The new zone has just closed and must wait 180 + 60 seconds.
    hass.states.values.pop("switch.new")
    hass.states.set("switch.new", "off")
    hass.states.set("switch.source", "off")
    original_call = hass.services.async_call

    async def call(domain, service, data, **kwargs):
        if delayed_feedback and service == "turn_on" and data.get("entity_id") == "switch.new":
            hass.calls.append((clock.now, service, "switch.new"))
            return  # HA accepted the call; ESPHome confirmation has not arrived.
        await original_call(domain, service, data, **kwargs)

    hass.services.async_call = call

    async def tick(seconds=0):
        clock.advance(seconds)
        await manager._on_tick(None)
        for _ in range(8):
            await asyncio.sleep(0)

    try:
        await tick()
        await tick(180)
        await tick(30)
        assert hass.states.get("switch.source").state == "on", "Source did not start as expected"
        started = clock.now
        await tick(30)
        interrupted = hass.states.get("switch.source").state == "off"
        old_closed = hass.states.get("switch.old").state == "off"
        new_confirmed = hass.states.get("switch.new").state == "on"
        result = {"delayed_feedback": delayed_feedback, "source_interrupted": interrupted,
                  "source_run_s": clock.now - started, "old_path_closed": old_closed,
                  "new_path_confirmed": new_confirmed, "plant_state": manager._plant_state}
        print(result)
        return not interrupted and (not old_closed or new_confirmed)
    finally:
        for task in hass.tasks:
            task.cancel()
        await asyncio.gather(*hass.tasks, return_exceptions=True)


async def main():
    instant = await probe(False)
    delayed = await probe(True)
    print("PASS: immediate feedback control" if instant else "FAIL: immediate feedback control")
    print("PASS: planned handover retains a confirmed path" if delayed else
          "FAIL: planned handover loses its confirmed path and stops the source after 30 seconds")
    return 0 if instant and delayed else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
