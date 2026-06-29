from __future__ import annotations

import logging, time
from datetime import timedelta
from typing import Dict, Any, List, Optional
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval, async_call_later
from homeassistant.const import SERVICE_TURN_ON, SERVICE_TURN_OFF
from homeassistant.core import DOMAIN as HA_DOMAIN

from .const import (
    DOMAIN, EVT_ZONE_STATUS, EVT_ZONE_SCHEDULE, EVT_HYDRONICS_DEMAND,
    CONF_T_CYCLE_SECONDS, CONF_T_CYCLE_MIN, CONF_T_CYCLE_MAX,
    CONF_PACKING_MODE, CONF_RH_ALERT, CONF_RH_FAULT, CONF_DP_SAFETY_MARGIN,
    CONF_RH_FAULT_CLEAR_HYST,
    DEFAULTS
)
from .config_flow import get_current_config
from .helpers import co_mode_from_entity

_LOGGER = logging.getLogger(__name__)

class ZoneManager:
    """Central coordinator for zone scheduling and source control."""

    def __init__(self, hass: HomeAssistant, entry):
        self.hass = hass
        self.entry = entry
        # Use unified config loading that merges options over data
        self._options = get_current_config(entry)
        self._zones: Dict[str, Dict[str, Any]] = {}  # last status per zone
        self._unsub_bus = None
        self._unsub_tick = None

        # Cycle state
        self._t_cycle = int(self._options.get(CONF_T_CYCLE_SECONDS, DEFAULTS[CONF_T_CYCLE_SECONDS]))
        self._packing = self._options.get(CONF_PACKING_MODE, DEFAULTS[CONF_PACKING_MODE])
        self._cycle_active = False
        self._cycle_start = 0.0
        self._slots: Dict[str, Dict[str, float]] = {}  # zone_id -> {start_offset, t_on}

    async def async_start(self):
        """Start listening for zone status and ticking the cycle."""
        self._unsub_bus = self.hass.bus.async_listen(EVT_ZONE_STATUS, self._on_zone_status)
        self._unsub_tick = async_track_time_interval(self.hass, self._on_tick, timedelta(seconds=1))
        _LOGGER.info("ZoneManager started: t_cycle=%ss, packing=%s", self._t_cycle, self._packing)

    async def async_stop(self):
        """Stop timers and listeners."""
        if self._unsub_bus:
            self._unsub_bus()
            self._unsub_bus = None
        if self._unsub_tick:
            self._unsub_tick()
            self._unsub_tick = None
        _LOGGER.info("ZoneManager stopped")

    @callback
    def _on_zone_status(self, event):
        data: dict = event.data or {}
        zid = data.get("zone_id")
        if not zid:
            return
        self._zones[zid] = data

    async def _on_tick(self, now):
        """Cycle state machine (PLAN → START/RUN → STOP). Runs every second."""
        system_mode = co_mode_from_entity(self.hass, self._options)
        if system_mode == "OFF":
            if self._cycle_active:
                await self._stop_cycle()
            return

        if not self._cycle_active:
            # PLAN: decide if we need to run a cycle
            plan = self._plan_cycle()
            if plan:
                await self._start_cycle(plan)
        else:
            # Check if cycle should end
            elapsed = time.time() - self._cycle_start
            if elapsed >= self._t_cycle:
                await self._stop_cycle()

    def _plan_cycle(self) -> Optional[Dict[str, Dict[str, float]]]:
        """Compute t_on per zone with RH/dew protection and return slot map or None."""

        zones = list(self._zones.values())
        if not zones:
            return None

        # Read options
        rh_alert = float(self._options.get(CONF_RH_ALERT, DEFAULTS[CONF_RH_ALERT]))
        rh_fault = float(self._options.get(CONF_RH_FAULT, DEFAULTS[CONF_RH_FAULT]))
        rh_clear = float(self._options.get(CONF_RH_FAULT_CLEAR_HYST, DEFAULTS[CONF_RH_FAULT_CLEAR_HYST]))
        dp_margin = float(self._options.get(CONF_DP_SAFETY_MARGIN, DEFAULTS[CONF_DP_SAFETY_MARGIN]))

        # Collect COOL/HEAT mode (we assume all VTs use same global mode)
        # Take the most recent co_mode present.
        co_mode = None
        for z in zones:
            if z.get("co_mode"):
                co_mode = z["co_mode"]
                break
        if co_mode is None:
            co_mode = "HEAT"
        if co_mode == "OFF":
            return None

        wants: Dict[str, Dict[str, float]] = {}
        any_demand = False

        # Compute p_i basic from delta (COOL: negative delta means too hot)
        for z in zones:
            zid = z["zone_id"]
            # Base eligibility checks
            if z.get("manual_off"):
                continue
            if not z.get("eligible_window", True):
                continue
            support = (z.get("support_mode") or "BOTH").upper()
            if (co_mode == "COOL" and support not in ("COOL", "BOTH")) or (co_mode == "HEAT" and support not in ("HEAT","BOTH")):
                continue

            t_air = z.get("t_air")
            delta = z.get("delta_air")  # target - t_air
            rh = z.get("rh")
            t_floor = z.get("t_floor")
            t_dew = z.get("dew_point")

            # RH fault interlock (COOL only)
            rh_fault_active = False
            if co_mode == "COOL" and rh is not None and rh >= rh_fault:
                rh_fault_active = True
                continue  # skip this zone fully

            # Basic proportional demand
            p = 0.0
            if delta is not None:
                if co_mode == "HEAT":
                    # Need heat if delta > 0
                    p = max(0.0, min(1.0, delta / 1.5))
                else:
                    # Need cool if delta < 0 -> use -delta
                    p = max(0.0, min(1.0, (-delta) / 1.5))

            # RH alert derating (COOL only)
            if co_mode == "COOL" and rh is not None and rh >= rh_alert and rh < rh_fault:
                # Linear derate: at alert => 1.0; at fault => 0.5
                frac = (rh - rh_alert) / max(1e-6, (rh_fault - rh_alert))
                derate = 1.0 - frac * 0.5
                p *= max(0.5, min(1.0, derate))

            # Dew guard derating
            if co_mode == "COOL" and (t_dew is not None):
                # if floor temp available, use that as surface
                surface = t_floor if (t_floor is not None) else (t_air if t_air is not None else None)
                if surface is not None:
                    dri = surface - t_dew
                    if dri <= 0.0:
                        p = 0.0  # hard interlock
                    elif dri < dp_margin:
                        scale = max(0.0, min(1.0, dri / dp_margin))
                        p *= scale

            if p <= 0.0:
                continue

            any_demand = True

            # Translate to t_on (respect zone min on/off and actuator timings if provided)
            t_on = p * self._t_cycle
            limits = z.get("limits", {})
            zone_min_on = float(limits.get("zone_min_on_s", 180))
            open_s = float(z.get("actuator", {}).get("open_s", 20))
            if t_on < (zone_min_on + open_s):
                t_on = zone_min_on + open_s

            wants[zid] = {"p": p, "t_on": t_on}

        return wants if any_demand else None

    async def _start_cycle(self, wants: Dict[str, Dict[str, float]]):
        """Start the cycle, schedule actuators, and publish hydronics demand."""
        self._cycle_active = True
        self._cycle_start = time.time()
        self._slots = {}

        # For MVP we do simultaneous packing: offset = 0 for all
        for zid, w in wants.items():
            self._slots[zid] = {"start_off": 0.0, "t_on": w["t_on"]}

        # Turn on all zones with open delay, and start source warmup if you add it later
        for zid, slot in self._slots.items():
            z = self._zones.get(zid, {})
            act = z.get("actuator", {})
            ent = act.get("entity_id")
            if ent:
                await self.hass.services.async_call(HA_DOMAIN, SERVICE_TURN_ON, {"entity_id": ent}, blocking=False)

        # Hydronics demand (basic)
        demand_ratio = 0.0
        if wants:
            demand_ratio = sum(w["p"] for w in wants.values()) / max(1, len(wants))
        payload = {
            "cycle_id": int(self._cycle_start),
            "mode": self._zones[next(iter(self._zones))].get("co_mode", "HEAT"),
            "demand_ratio": round(demand_ratio, 3),
        }
        self.hass.bus.async_fire(EVT_HYDRONICS_DEMAND, payload)

        _LOGGER.info("Cycle START: %d zones, demand_ratio=%.2f", len(self._slots), demand_ratio)

        # Schedule per-zone turn-off at end of each t_on
        for zid, slot in self._slots.items():
            when = self._cycle_start + slot["start_off"] + slot["t_on"]
            delay = max(0.0, when - time.time())
            async_call_later(self.hass, delay, lambda *_: self.hass.async_create_task(self._turn_off_zone(zid)))

    async def _turn_off_zone(self, zid: str):
        z = self._zones.get(zid, {})
        act = z.get("actuator", {})
        ent = act.get("entity_id")
        if ent:
            await self.hass.services.async_call(HA_DOMAIN, SERVICE_TURN_OFF, {"entity_id": ent}, blocking=False)

    async def _stop_cycle(self):
        """Stop the cycle and ensure all zones are off."""
        self._cycle_active = False
        # Safety: ensure all actuators OFF
        for zid, z in self._zones.items():
            ent = (z.get("actuator") or {}).get("entity_id")
            if ent:
                await self.hass.services.async_call(HA_DOMAIN, SERVICE_TURN_OFF, {"entity_id": ent}, blocking=False)
        _LOGGER.info("Cycle STOP")
