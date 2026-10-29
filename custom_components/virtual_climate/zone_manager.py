from __future__ import annotations

import asyncio
import logging
import time
from copy import deepcopy
from datetime import timedelta
from typing import Callable, Dict, Any, List, Optional
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_call_later, async_track_state_change_event, async_track_time_interval
from homeassistant.const import SERVICE_TURN_ON, SERVICE_TURN_OFF
from homeassistant.core import DOMAIN as HA_DOMAIN

from .const import (
    DOMAIN, EVT_HYDRONICS_DEMAND, THERMAL_UPDATE_SECONDS, CONF_GLOBAL_CO_MODE_ENTITY,
    CONF_T_CYCLE_SECONDS, CONF_T_CYCLE_MIN, CONF_T_CYCLE_MAX,
    CONF_PACKING_MODE, CONF_RH_ALERT, CONF_RH_FAULT, CONF_DP_SAFETY_MARGIN,
    CONF_RH_FAULT_CLEAR_HYST, CONF_HEATING_SOURCE_ENTITY,
    CONF_COOLING_SOURCE_ENTITY, CONF_CHANGEOVER_ENTITY,
    CONF_CIRCULATION_PUMP_ENTITY, CONF_TARGET_SUPPLY_TEMPERATURE_ENTITY,
    CONF_HEATING_SUPPLY_TARGET, CONF_COOLING_SUPPLY_TARGET,
    CONF_PUMP_START_DELAY_SECONDS, CONF_HEATING_SOURCE_START_DELAY_SECONDS,
    CONF_COOLING_SOURCE_START_DELAY_SECONDS, CONF_MINIMUM_RUN_TIME_SECONDS,
    CONF_PUMP_POST_RUN_SECONDS, CONF_MINIMUM_OFF_TIME_SECONDS,
    DEFAULTS, EVENT_ENTRY_ID
)
from .config_flow import get_current_config
from .helpers import co_mode_from_entity
from .supply_regulator import SupplyRegulator

_LOGGER = logging.getLogger(__name__)

GLOBAL_DEMAND_RATIO_PRECISION = 2
GLOBAL_DEMAND_RATIO_MIN_DELTA = 0.02
HANDOVER_CONFIRM_TIMEOUT_SECONDS = 30

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
        self._unsub_transition = None
        self._zone_refreshers = {}
        self._zone_listeners = {}
        self._last_zone_diagnostics = {}
        self._last_notified_diagnostics = None
        self._last_thermal_update = None
        self._last_control_inputs = None
        self._last_system_mode = None
        self._cached_wants = None
        self._started = False
        self._evaluation_task = None
        self._evaluation_requested = False

        # Cycle state
        self._t_cycle = int(self._options.get(CONF_T_CYCLE_SECONDS, DEFAULTS[CONF_T_CYCLE_SECONDS]))
        self._packing = self._options.get(CONF_PACKING_MODE, DEFAULTS[CONF_PACKING_MODE])
        self._cycle_active = False
        self._cycle_start = 0.0
        self._cycle_mode: Optional[str] = None
        self._cycle_length = int(self._options.get(CONF_T_CYCLE_SECONDS, DEFAULTS[CONF_T_CYCLE_SECONDS]))
        self._slots: Dict[str, Dict[str, float]] = {}  # zone_id -> {start_offset, t_on}
        self._zone_last_on_at: Dict[str, float] = {}
        self._zone_last_off_at: Dict[str, float] = {}
        self._zone_observed: Dict[str, bool | None] = {}
        self._zone_commands: Dict[str, tuple[bool, float]] = {}
        self._desired_on: set[str] = set()
        self._plant_hold_zones: set[str] = set()
        self._handover_hold_zones: set[str] = set()
        self._handover_deadline = 0.0
        self._plant_outputs_observed = False
        self._tick_lock = asyncio.Lock()
        self._stopped = False
        self._plant_state = "off"  # off | starting | running | stopping
        self._plant_mode: Optional[str] = None
        self._plant_started_at = 0.0
        self._plant_stopped_at = 0.0
        self._plant_session = 0
        self._plant_start_task: Optional[asyncio.Task] = None
        self._plant_stop_task: Optional[asyncio.Task] = None
        self._global_diag: Dict[str, Any] = {}
        self._listeners: list[Callable[[], None]] = []
        self.supply = SupplyRegulator(hass, entry.entry_id)

    def _zone_slot_is_running(self, zid: str, now_ts: float | None = None) -> bool:
        """Return whether a scheduled zone is within its active slot right now."""
        if not self._cycle_active:
            return False
        slot = self._slots.get(zid)
        if not slot:
            return False
        if now_ts is None:
            now_ts = time.time()
        start_at = self._cycle_start + float(slot.get("start_off", 0.0) or 0.0)
        end_at = start_at + float(slot.get("t_on", 0.0) or 0.0)
        return start_at <= now_ts < end_at

    async def async_start(self):
        """Start listening for zone status and ticking the cycle."""
        self._stopped = False
        self._started = True
        await self.supply.async_start(self._options)
        observed = {z.get("switch_actuator") for z in self._options.get("zones", [])}
        observed.update(self._options.get(key) for key in (
            CONF_GLOBAL_CO_MODE_ENTITY, CONF_HEATING_SOURCE_ENTITY,
            CONF_COOLING_SOURCE_ENTITY, CONF_CIRCULATION_PUMP_ENTITY))
        if observed - {None}:
            self._unsub_bus = async_track_state_change_event(
                self.hass, list(observed - {None}), self._on_output_change)
        self._unsub_tick = async_track_time_interval(
            self.hass, self._on_thermal_tick, timedelta(seconds=THERMAL_UPDATE_SECONDS))
        self._refresh_global_diagnostics(system_mode=co_mode_from_entity(self.hass, self._options), phase="startup")
        await self._on_tick(None)
        _LOGGER.info("ZoneManager started: t_cycle=%ss, packing=%s", self._t_cycle, self._packing)

    async def async_stop(self):
        """Stop timers and listeners."""
        self._stopped = True
        self._started = False
        if self._evaluation_task:
            self._evaluation_task.cancel()
            await asyncio.gather(self._evaluation_task, return_exceptions=True)
            self._evaluation_task = None
        async with self._tick_lock:
            await self._async_shutdown()

    async def _async_shutdown(self):
        if self._unsub_bus:
            self._unsub_bus()
            self._unsub_bus = None
        if self._unsub_tick:
            self._unsub_tick()
            self._unsub_tick = None
        if self._unsub_transition:
            self._unsub_transition()
            self._unsub_transition = None
        tasks = [task for task in (self._plant_start_task, self._plant_stop_task) if task]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._plant_start_task = None
        self._plant_stop_task = None
        await self._set_switch_state(self._options.get(CONF_HEATING_SOURCE_ENTITY), False)
        await self._set_switch_state(self._options.get(CONF_COOLING_SOURCE_ENTITY), False)
        await self._set_switch_state(self._options.get(CONF_CIRCULATION_PUMP_ENTITY), False)
        self._plant_hold_zones.clear()
        self._clear_handover()
        self._observe_actuators()
        for zid in self._zones:
            await self._command_zone(zid, False)
        self._cycle_active = False
        self._slots = {}
        self._plant_state = "off"
        self._plant_mode = None
        await self.supply.async_stop()
        self._refresh_global_diagnostics(system_mode=co_mode_from_entity(self.hass, self._options), phase="stopped")
        _LOGGER.info("ZoneManager stopped")

    @callback
    def async_set_zone_status(self, data):
        """Receive sampled status directly; internal telemetry never enters Recorder."""
        if data.get(EVENT_ENTRY_ID) != self.entry.entry_id:
            return
        zid = data.get("zone_id")
        if not zid:
            return
        zone = self._zones.setdefault(zid, {"last_block_reasons": []})
        zone.update(data)

    @callback
    def async_register_zone(self, zid, refresh, listener):
        self._zone_refreshers[zid] = refresh
        self._zone_listeners[zid] = listener

        @callback
        def remove():
            self._zone_refreshers.pop(zid, None)
            self._zone_listeners.pop(zid, None)
            self._last_zone_diagnostics.pop(zid, None)
            self._zones.pop(zid, None)
        return remove

    @callback
    def _on_output_change(self, event):
        self.async_request_evaluation()

    @callback
    def async_request_evaluation(self):
        """Coalesce explicit commands and output feedback, without a polling loop."""
        if not self._started or self._stopped:
            return
        self._evaluation_requested = True
        if self._evaluation_task is None:
            # HA starts tasks eagerly by default. Defer this one so its cleanup
            # cannot run before we store the task, and output changes coalesce.
            self._evaluation_task = self.hass.async_create_task(
                self._async_evaluate_requested(), eager_start=False)

    async def _async_evaluate_requested(self):
        try:
            while self._evaluation_requested and not self._stopped:
                self._evaluation_requested = False
                await self._on_tick(None)
        finally:
            self._evaluation_task = None

    def _schedule_next_transition(self):
        """Wake at slot/valve deadlines, not once a second to recalculate demand."""
        if self._unsub_transition:
            self._unsub_transition()
            self._unsub_transition = None
        if not self._started or self._stopped:
            return
        now = time.time()
        deadlines = []
        if self._cycle_active:
            deadlines.append(self._cycle_start + self._cycle_length)
            for slot in self._slots.values():
                start = self._cycle_start + slot["start_off"]
                deadlines.extend((start, start + slot["t_on"]))
        for zid, zone in self._zones.items():
            actual = self._actuator_state(zid)
            if actual is True:
                on_at = self._zone_last_on_at.get(zid, now)
                deadlines.extend((on_at + self._minimum_on(zid),
                                  on_at + float(zone.get("actuator", {}).get("open_s", 20))))
            elif zid in (self._cached_wants or {}):
                deadlines.append(self._restart_at(zid))
            command = self._zone_commands.get(zid)
            if command and actual is not (zid in self._desired_on):
                deadlines.append(command[1] + 5)
        if self._handover_deadline:
            deadlines.append(self._handover_deadline)
        future = [deadline for deadline in deadlines if deadline > now + 0.001]
        if future:
            self._unsub_transition = async_call_later(self.hass, min(future) - now, self._on_transition)

    async def _on_transition(self, now):
        self._unsub_transition = None
        await self._on_tick(now)

    @callback
    def async_add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        self._listeners.append(listener)

        @callback
        def _remove_listener() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return _remove_listener

    @callback
    def get_global_diagnostics(self) -> Dict[str, Any]:
        return dict(self._global_diag)

    @callback
    def _refresh_global_diagnostics(
        self,
        demand_ratio: float | None = None,
        system_mode: str | None = None,
        phase: str | None = None,
    ) -> None:
        if demand_ratio is None:
            demand_ratio = float(self._global_diag.get("aggregated_demand_ratio", 0.0) or 0.0)
        if system_mode is None:
            system_mode = co_mode_from_entity(self.hass, self._options)
        if phase is None:
            phase = self._global_diag.get("coordinator_phase", "idle")

        zone_states = list(self._zones.values())
        scheduled_zones = sum(1 for z in zone_states if z.get("zone_id") in self._slots)
        running_zones = sum(self._actuator_state(z.get("zone_id")) is True for z in zone_states)
        blocked_zones = sum(
            z.get("coordinator_status") == "blocked" or self._waiting_for_restart(z.get("zone_id"))
            for z in zone_states
        )
        previous_ratio = float(self._global_diag.get("aggregated_demand_ratio", 0.0) or 0.0)
        rounded_ratio = round(float(demand_ratio), GLOBAL_DEMAND_RATIO_PRECISION)
        if demand_ratio > 0:
            rounded_ratio = max(10 ** -GLOBAL_DEMAND_RATIO_PRECISION, rounded_ratio)
        if rounded_ratio > 0 and previous_ratio > 0 and abs(rounded_ratio - previous_ratio) < GLOBAL_DEMAND_RATIO_MIN_DELTA:
            rounded_ratio = previous_ratio

        self._global_diag = {
            "system_mode": system_mode,
            "coordinator_phase": phase,
            "cycle_active": self._cycle_active,
            "cycle_length_s": self._cycle_length,
            "packing_mode": self._packing,
            "aggregated_demand_ratio": rounded_ratio,
            "plant_state": self._plant_state,
            "plant_mode": self._plant_mode or "OFF",
            "total_zones": len(zone_states),
            "scheduled_zones": scheduled_zones,
            "running_zones": running_zones,
            "scheduled_running_zones": sum(self._zone_slot_is_running(zid) for zid in self._slots),
            "actuator_mismatches": sum(
                self._actuator_state(zid) is not None and self._actuator_state(zid) != (zid in self._desired_on)
                for zid in self._zones
            ),
            "unavailable_actuators": sum(self._actuator_state(zid) is None for zid in self._zones),
            "blocked_zones": blocked_zones,
            **self.supply.diagnostics,
        }
        if self._last_notified_diagnostics == self._global_diag:
            return
        self._last_notified_diagnostics = deepcopy(self._global_diag)
        for listener in list(self._listeners):
            listener()

    async def _on_thermal_tick(self, now):
        await self._on_tick(now, refresh=True)

    async def _on_tick(self, now, *, refresh=False):
        """Serialize planning and actuator reconciliation on the HA event loop."""
        async with self._tick_lock:
            if not self._stopped:
                await self._async_tick(refresh=refresh)
                self._schedule_next_transition()

    async def _async_tick(self, *, refresh=False):
        self._options = get_current_config(self.entry)
        system_mode = co_mode_from_entity(self.hass, self._options)
        now = time.time()
        # Coalesce a periodic sample with a coincident slot/output callback.
        thermal_due = ((refresh and (self._last_thermal_update is None
                                    or now - self._last_thermal_update >= 1))
                       or self._last_thermal_update is None
                       or now - self._last_thermal_update >= THERMAL_UPDATE_SECONDS
                       or now < self._last_thermal_update
                       or system_mode != self._last_system_mode)
        if thermal_due:
            for refresh_zone in list(self._zone_refreshers.values()):
                await refresh_zone(None, publish=False, control_sample=True)
            self._last_thermal_update = now
        self._last_system_mode = system_mode
        inputs = (self._options, {
            zid: {key: z.get(key) for key in (
                "delta_air", "t_air", "t_air_raw", "t_floor", "rh", "dew_point", "manual_off",
                "eligible_window", "support_mode", "actuator", "limits")}
            for zid, z in self._zones.items()})
        replan = thermal_due or inputs != self._last_control_inputs
        if replan:
            self._last_control_inputs = deepcopy(inputs)
        self._observe_actuators()
        await self._recover_plant_outputs()
        if system_mode == "OFF":
            if replan:
                await self._update_supply(system_mode, force=thermal_due)
            self._cached_wants = None
            await self._request_plant_stop("global_off")
            await self._stop_cycle()
            self._publish_zone_diagnostics({}, system_mode, "global_off", sampled=thermal_due)
            return

        if ((self._cycle_mode and self._cycle_mode != system_mode) or
                (self._plant_mode and self._plant_mode != system_mode and self._plant_state != "off")):
            self._cached_wants = None
            self._last_control_inputs = None
            if replan:
                await self._update_supply(system_mode, force=thermal_due)
            await self._request_plant_stop("mode_change")
            await self._stop_cycle()
            self._publish_zone_diagnostics({}, system_mode, "mode_change", sampled=thermal_due)
            return

        if replan:
            self._cached_wants = self._plan_cycle()
        plan = self._cached_wants
        if not self._cycle_active or time.time() - self._cycle_start >= self._cycle_length:
            if plan and self._plant_state != "stopping":
                await self._start_cycle(plan)
            else:
                self._cycle_active = False
                self._slots = {}

        # Stop the source before closing its last normal circulation path.
        planned_flow = any(self._zone_slot_is_running(zid) and zid in (plan or {}) for zid in self._slots)
        if not planned_flow:
            await self._request_plant_stop("no_demand")
        await self._reconcile_zones(plan or {})
        if replan:
            await self._update_supply(system_mode, force=thermal_due)
        if self._plant_state == "running" and self._plant_mode == system_mode:
            await self.supply.async_write(self._options, system_mode)

        if self._plant_state in ("running", "stopping") and not self._flow_zones(require_open=True):
            await self._request_plant_stop("no_flow")
        elif plan and planned_flow and self._flow_zones():
            await self._request_plant_start(system_mode, plan)
        elif self._plant_state == "starting" and not self._flow_zones():
            await self._request_plant_stop("no_flow")
        self._publish_zone_diagnostics(plan or {}, system_mode, "running" if self._cycle_active else "idle",
                                       sampled=thermal_due)

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

        co_mode = co_mode_from_entity(self.hass, self._options)
        if co_mode == "OFF":
            return None

        wants: Dict[str, Dict[str, float]] = {}
        any_demand = False
        cycle_length = self._cycle_length

        # Compute p_i basic from delta (COOL: negative delta means too hot)
        for z in zones:
            zid = z["zone_id"]
            block_reasons: List[str] = []
            z["requested_p"] = 0.0
            z["requested_t_on"] = 0.0
            z["scheduled_t_on"] = 0.0
            z["start_offset"] = None
            z["arbitration_rank"] = None
            z["coordinator_status"] = "idle"
            # Base eligibility checks
            if z.get("manual_off"):
                block_reasons.append("manual_off")
                z["last_block_reasons"] = block_reasons
                z["coordinator_status"] = "blocked"
                continue
            if not z.get("eligible_window", True):
                block_reasons.append("window_open")
                z["last_block_reasons"] = block_reasons
                z["coordinator_status"] = "blocked"
                continue
            support = (z.get("support_mode") or "BOTH").upper()
            if (co_mode == "COOL" and support not in ("COOL", "BOTH")) or (co_mode == "HEAT" and support not in ("HEAT","BOTH")):
                block_reasons.append("unsupported_mode")
                z["last_block_reasons"] = block_reasons
                z["coordinator_status"] = "blocked"
                continue

            t_air = z.get("t_air")
            delta = z.get("delta_air")  # target - t_air
            rh = z.get("rh")
            t_floor = z.get("t_floor")
            t_dew = z.get("dew_point")

            if delta is None or t_air is None:
                z["last_block_reasons"] = ["air_sensor_unavailable"]
                z["coordinator_status"] = "blocked"
                continue

            # RH fault interlock (COOL only)
            rh_fault_active = False
            if co_mode == "COOL" and rh is not None and rh >= rh_fault:
                rh_fault_active = True
                block_reasons.append("rh_fault")
                z["last_block_reasons"] = block_reasons
                z["coordinator_status"] = "blocked"
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
                surface = t_floor if t_floor is not None else z.get("t_air_raw", t_air)
                if surface is not None:
                    dri = surface - t_dew
                    if dri <= 0.0:
                        block_reasons.append("dew_guard_lockout")
                        p = 0.0  # hard interlock
                    elif dri < dp_margin:
                        scale = max(0.0, min(1.0, dri / dp_margin))
                        p *= scale

            limits = z.get("limits", {})
            floor_limits = (limits.get("floor") or {}) if isinstance(limits, dict) else {}
            if t_floor is not None and floor_limits:
                if co_mode == "HEAT":
                    heat_max = floor_limits.get("heat_max")
                    if heat_max is not None and t_floor >= float(heat_max):
                        block_reasons.append("floor_heat_max")
                        p = 0.0
                elif co_mode == "COOL":
                    cool_min = floor_limits.get("cool_min")
                    if cool_min is not None and t_floor <= float(cool_min):
                        block_reasons.append("floor_cool_min")
                        p = 0.0

            if p <= 0.0:
                z["requested_p"] = 0.0
                z["requested_t_on"] = 0.0
                z["last_block_reasons"] = block_reasons or ["no_demand"]
                z["coordinator_status"] = "blocked" if block_reasons else "idle"
                continue

            any_demand = True
            z["last_block_reasons"] = []

            # Translate to t_on (respect zone min on/off and actuator timings if provided)
            t_on = p * cycle_length
            zone_min_on = float(limits.get("zone_min_on_s", 180))
            open_s = float(z.get("actuator", {}).get("open_s", 20))
            if t_on < (zone_min_on + open_s):
                t_on = zone_min_on + open_s

            z["requested_p"] = round(p, 4)
            z["requested_t_on"] = round(t_on, 1)
            z["coordinator_status"] = "candidate"
            wants[zid] = {"p": p, "t_on": t_on}

        return wants if any_demand else None

    def _compute_cycle_length(self, zones: List[Dict[str, Any]]) -> int:
        base_cycle = int(self._options.get(CONF_T_CYCLE_SECONDS, DEFAULTS[CONF_T_CYCLE_SECONDS]))
        min_cycle = int(self._options.get(CONF_T_CYCLE_MIN, DEFAULTS[CONF_T_CYCLE_MIN]))
        max_cycle = int(self._options.get(CONF_T_CYCLE_MAX, DEFAULTS[CONF_T_CYCLE_MAX]))

        if min_cycle > max_cycle:
            min_cycle, max_cycle = max_cycle, min_cycle

        if min_cycle == max_cycle:
            return max(1, min_cycle)

        supported = [z for z in zones if not self._hard_blocked(z["zone_id"])]
        if not supported:
            return max(min_cycle, min(max_cycle, base_cycle))

        demand_values = [float(z.get("requested_p", 0.0)) for z in supported]

        if not demand_values:
            return max(min_cycle, min(max_cycle, base_cycle))

        avg_demand = sum(demand_values) / len(demand_values)
        dynamic_cycle = min_cycle + (max_cycle - min_cycle) * avg_demand
        return max(1, int(round(dynamic_cycle)))

    def _cancel_task(self, task: Optional[asyncio.Task]) -> None:
        if task and not task.done():
            task.cancel()

    def _plant_control_enabled(self) -> bool:
        return any(
            self._options.get(key)
            for key in (
                CONF_HEATING_SOURCE_ENTITY,
                CONF_COOLING_SOURCE_ENTITY,
                CONF_CHANGEOVER_ENTITY,
                CONF_CIRCULATION_PUMP_ENTITY,
                CONF_TARGET_SUPPLY_TEMPERATURE_ENTITY,
            )
        )

    async def _recover_plant_outputs(self):
        """Drain outputs left on across a restart before starting a new session."""
        if self._plant_outputs_observed:
            return
        self._plant_outputs_observed = True
        active = []
        for mode in ("HEAT", "COOL"):
            entity = self._source_entity_for_mode(mode)
            state = self.hass.states.get(entity) if entity else None
            if state and state.state == "on":
                active.append((mode, state))
        pump = self._options.get(CONF_CIRCULATION_PUMP_ENTITY)
        pump_state = self.hass.states.get(pump) if pump else None
        if not active and not (pump_state and pump_state.state == "on"):
            return
        preferred_mode = co_mode_from_entity(self.hass, self._options)
        changeover = self._options.get(CONF_CHANGEOVER_ENTITY)
        changeover_state = self.hass.states.get(changeover) if changeover else None
        if changeover_state and changeover_state.state in ("on", "off"):
            preferred_mode = "COOL" if changeover_state.state == "on" else "HEAT"
        selected = next((item for item in active if item[0] == preferred_mode), active[0] if active else None)
        self._plant_mode = selected[0] if selected else "HEAT"
        self._plant_state = "running"
        if active:
            changed = getattr(selected[1], "last_changed", None)
            self._plant_started_at = changed.timestamp() if changed else time.time()
        reason = "no_flow" if len({state.entity_id for _, state in active}) > 1 else "startup_recovery"
        await self._request_plant_stop(reason)

    def _plant_mode_supported(self, mode: str) -> bool:
        return self._source_entity_for_mode(mode) is not None

    def _source_entity_for_mode(self, mode: str) -> str | None:
        heat_ent = self._options.get(CONF_HEATING_SOURCE_ENTITY)
        cool_ent = self._options.get(CONF_COOLING_SOURCE_ENTITY)
        changeover_ent = self._options.get(CONF_CHANGEOVER_ENTITY)
        if mode == "HEAT":
            return heat_ent
        if cool_ent:
            return cool_ent
        if heat_ent and changeover_ent:
            return heat_ent
        return None

    async def _set_switch_state(self, entity_id: str | None, turn_on: bool) -> None:
        if not entity_id:
            return
        service = SERVICE_TURN_ON if turn_on else SERVICE_TURN_OFF
        await self.hass.services.async_call(
            HA_DOMAIN,
            service,
            {"entity_id": entity_id},
            blocking=True,
        )

    async def _set_changeover_for_mode(self, mode: str) -> None:
        entity_id = self._options.get(CONF_CHANGEOVER_ENTITY)
        if not entity_id:
            return
        # Assumption for MVP: ON selects COOL, OFF selects HEAT.
        await self._set_switch_state(entity_id, mode == "COOL")

    async def _update_supply(self, mode: str, force=False):
        await self.supply.async_update(
            self._options, mode, self._zones,
            controlled=self._source_entity_for_mode(mode) is not None if mode != "OFF" else False,
            running=self._plant_state == "running" and self._plant_mode == mode,
            force=force,
        )

    async def _set_target_supply_for_mode(self, mode: str) -> None:
        await self._update_supply(mode, force=True)
        if not await self.supply.async_write(self._options, mode, force=True):
            raise ValueError("Supply target command has not succeeded")

    async def _request_plant_start(self, mode: str, wants: Dict[str, Dict[str, float]]) -> None:
        if not self._plant_control_enabled():
            return
        if not self._plant_mode_supported(mode):
            _LOGGER.info("Plant start skipped: no outputs configured for mode=%s", mode)
            return

        demand_ratio = 0.0
        if wants:
            demand_ratio = sum(w["p"] for w in wants.values()) / max(1, len(wants))

        if self._plant_state == "running" and self._plant_mode == mode:
            return
        if self._plant_state == "starting" and self._plant_mode == mode:
            return
        if not self.supply.retry_ready():
            return

        # Complete source shutdown and pump post-run before changing mode/restarting.
        if self._plant_state == "stopping":
            return

        if self._plant_state in ("running", "starting") and self._plant_mode != mode:
            await self._request_plant_stop("mode_change")
            return

        self._plant_hold_zones.clear()
        self._plant_state = "starting"
        self._plant_mode = mode
        self._plant_start_task = self.hass.async_create_task(
            self._async_start_plant(mode, demand_ratio)
        )

    async def _request_plant_stop(self, reason: str) -> None:
        if not self._plant_control_enabled():
            return
        if self._plant_state == "off":
            return
        if self._plant_stop_task and not self._plant_stop_task.done():
            if reason != "no_flow":
                return
            self._cancel_task(self._plant_stop_task)

        if self._plant_start_task is not asyncio.current_task():
            self._cancel_task(self._plant_start_task)
        self._plant_start_task = None
        self._clear_handover()
        self._plant_hold_zones.update(
            zid for zid in self._zones
            if self._actuator_state(zid) is True and not self._hard_blocked(zid)
        )
        if not self._plant_hold_zones:
            reason = "no_flow"
        self._plant_state = "stopping"
        self._plant_stop_task = self.hass.async_create_task(
            self._async_stop_plant(reason)
        )

    async def _async_start_plant(self, mode: str, demand_ratio: float) -> None:
        self._plant_session += 1
        session = self._plant_session
        self._plant_state = "starting"
        self._plant_mode = mode
        self._refresh_global_diagnostics(demand_ratio=demand_ratio, system_mode=mode)
        _LOGGER.info(
            "Plant START requested: session=%s mode=%s demand_ratio=%.2f",
            session,
            mode,
            demand_ratio,
        )
        try:
            min_off = int(self._options.get(CONF_MINIMUM_OFF_TIME_SECONDS, DEFAULTS[CONF_MINIMUM_OFF_TIME_SECONDS]))
            source_state = self.hass.states.get(self._source_entity_for_mode(mode))
            stopped_at = self._plant_stopped_at
            if source_state and source_state.state == "off":
                changed = getattr(source_state, "last_changed", None)
                if changed:
                    stopped_at = max(stopped_at, changed.timestamp())
            if stopped_at and min_off > 0:
                wait_off = max(0.0, (stopped_at + min_off) - time.time())
                if wait_off > 0:
                    _LOGGER.info("Plant waiting %.1fs for minimum off time", wait_off)
                    await asyncio.sleep(wait_off)

            await self._set_changeover_for_mode(mode)
            await self._set_target_supply_for_mode(mode)

            pump_delay = int(self._options.get(CONF_PUMP_START_DELAY_SECONDS, DEFAULTS[CONF_PUMP_START_DELAY_SECONDS]))
            source_delay_key = CONF_COOLING_SOURCE_START_DELAY_SECONDS if mode == "COOL" else CONF_HEATING_SOURCE_START_DELAY_SECONDS
            source_delay = int(self._options.get(source_delay_key, DEFAULTS[source_delay_key]))

            if pump_delay > 0:
                _LOGGER.info("Plant start delay before pump: %ss", pump_delay)
                await asyncio.sleep(pump_delay)
            if not self._flow_zones():
                await self._request_plant_stop("no_flow")
                return
            await self._set_switch_state(self._options.get(CONF_CIRCULATION_PUMP_ENTITY), True)

            additional_source_delay = max(0, source_delay - pump_delay, self._flow_open_delay())
            if additional_source_delay > 0:
                _LOGGER.info("Plant additional delay before %s source: %ss", mode, additional_source_delay)
                await asyncio.sleep(additional_source_delay)

            if not self._flow_zones(require_open=True):
                await self._request_plant_stop("no_flow")
                return

            # Conditions may have changed during valve opening / source delays.
            await self._set_target_supply_for_mode(mode)
            source_entity = self._source_entity_for_mode(mode)
            if mode == "HEAT":
                cool_ent = self._options.get(CONF_COOLING_SOURCE_ENTITY)
                if cool_ent and cool_ent != source_entity:
                    await self._set_switch_state(cool_ent, False)
            else:
                heat_ent = self._options.get(CONF_HEATING_SOURCE_ENTITY)
                if heat_ent and heat_ent != source_entity and self._options.get(CONF_COOLING_SOURCE_ENTITY):
                    await self._set_switch_state(heat_ent, False)
            await self._set_switch_state(source_entity, True)

            self._plant_started_at = time.time()
            self._plant_state = "running"
            self._refresh_global_diagnostics(system_mode=mode)
            _LOGGER.info("Plant START complete: session=%s mode=%s", session, mode)
        except asyncio.CancelledError:
            _LOGGER.debug("Plant START cancelled: session=%s", session)
            raise
        except Exception:
            _LOGGER.exception("Plant start failed: session=%s", session)
            await self._request_plant_stop("start_failed")
        finally:
            if self._plant_start_task is asyncio.current_task():
                self._plant_start_task = None
            self.async_request_evaluation()

    async def _async_stop_plant(self, reason: str) -> None:
        self._plant_state = "stopping"
        mode = self._plant_mode or "HEAT"
        self._refresh_global_diagnostics(system_mode=mode)
        _LOGGER.info("Plant STOP requested: mode=%s reason=%s", mode, reason)
        try:
            min_run = int(self._options.get(CONF_MINIMUM_RUN_TIME_SECONDS, DEFAULTS[CONF_MINIMUM_RUN_TIME_SECONDS]))
            if reason != "no_flow" and self._plant_started_at and min_run > 0:
                wait_run = max(0.0, (self._plant_started_at + min_run) - time.time())
                if wait_run > 0:
                    _LOGGER.info("Plant waiting %.1fs for minimum run time", wait_run)
                    await asyncio.sleep(wait_run)

            entities_to_turn_off = {
                self._options.get(CONF_HEATING_SOURCE_ENTITY),
                self._options.get(CONF_COOLING_SOURCE_ENTITY),
            }
            for entity_id in entities_to_turn_off:
                await self._set_switch_state(entity_id, False)

            post_run = int(self._options.get(CONF_PUMP_POST_RUN_SECONDS, DEFAULTS[CONF_PUMP_POST_RUN_SECONDS]))
            if reason != "no_flow" and post_run > 0 and self._options.get(CONF_CIRCULATION_PUMP_ENTITY):
                _LOGGER.info("Plant pump post-run: %ss", post_run)
                await asyncio.sleep(post_run)

            await self._set_switch_state(self._options.get(CONF_CIRCULATION_PUMP_ENTITY), False)

            self._plant_state = "off"
            self._plant_stopped_at = time.time()
            previous_mode = self._plant_mode
            self._plant_mode = None
            self._plant_started_at = 0.0
            self._plant_hold_zones.clear()
            self._refresh_global_diagnostics(system_mode=co_mode_from_entity(self.hass, self._options))
            _LOGGER.info("Plant STOP complete: previous_mode=%s reason=%s", previous_mode, reason)
        except asyncio.CancelledError:
            _LOGGER.debug("Plant STOP cancelled")
            raise
        except Exception:
            _LOGGER.exception("Plant stop failed; will retry on the next tick")
        finally:
            if self._plant_stop_task is asyncio.current_task():
                self._plant_stop_task = None
            self.async_request_evaluation()

    def _build_slots(self, wants: Dict[str, Dict[str, float]]) -> Dict[str, Dict[str, float]]:
        ordered = sorted(wants.items(), key=lambda item: (-item[1]["p"], item[0]))
        slots: Dict[str, Dict[str, float]] = {}
        spacing = self._cycle_length / max(1, len(ordered)) if self._packing == "staggered" else 0
        for index, (zid, w) in enumerate(ordered):
            minimum_on = self._minimum_on(zid)
            # Staggering is a preference; never shorten a pulse below its minimum.
            preferred_start = min(index * spacing, max(0, self._cycle_length - minimum_on))
            start_off = max(preferred_start, self._restart_at(zid) - self._cycle_start, 0)
            t_on = min(max(w["p"] * self._cycle_length, minimum_on), self._cycle_length - start_off)
            z = self._zones[zid]
            z["requested_t_on"] = round(max(w["p"] * self._cycle_length, minimum_on), 1)
            if t_on < minimum_on or t_on <= 0:
                z["coordinator_status"] = "blocked"
                z["last_block_reasons"] = ["zone_min_off" if self._restart_at(zid) > self._cycle_start else "cycle_capacity"]
                continue
            slots[zid] = {"start_off": round(start_off, 1), "t_on": round(t_on, 1), "rank": index + 1}
        return slots

    def _publish_zone_diagnostics(self, wants: Optional[Dict[str, Dict[str, float]]], system_mode: str, phase: str,
                                  *, sampled=False) -> None:
        # None means a state-only refresh; an empty mapping explicitly clears demand.
        demand_ratio = None if wants is None else self._demand_ratio(wants)
        self._refresh_global_diagnostics(demand_ratio=demand_ratio, system_mode=system_mode, phase=phase)
        if wants is None:
            demand_ratio = self._global_diag.get("aggregated_demand_ratio", 0.0)

        now_ts = time.time()
        for zid, z in self._zones.items():
            slot = self._slots.get(zid, {})
            block_reasons = list(z.get("last_block_reasons") or [])
            waiting_for_restart = self._waiting_for_restart(zid)
            if waiting_for_restart and "zone_min_off" not in block_reasons:
                block_reasons.append("zone_min_off")
            scheduled = zid in self._slots
            zone_status = z.get("coordinator_status", "idle")
            scheduled_running = self._zone_slot_is_running(zid, now_ts)
            actual = self._actuator_state(zid)
            is_running = actual is True
            if is_running:
                coordinator_status = "running"
            elif waiting_for_restart:
                coordinator_status = "waiting"
            elif scheduled:
                coordinator_status = "scheduled"
            else:
                coordinator_status = zone_status

            payload = {
                EVENT_ENTRY_ID: self.entry.entry_id,
                "zone_id": zid,
                "system_mode": system_mode,
                "active_co_mode": z.get("active_co_mode", z.get("co_mode")),
                "cycle_active": self._cycle_active,
                "cycle_length_s": self._cycle_length,
                "cycle_started_at": self._cycle_start if self._cycle_active else None,
                "packing_mode": self._packing,
                "coordinator_phase": phase,
                "coordinator_status": coordinator_status,
                "eligible": not block_reasons,
                "scheduled": scheduled,
                "running": is_running,
                "scheduled_running": scheduled_running,
                "actuator_state": "unknown" if actual is None else ("on" if actual else "off"),
                "actuator_commanded_state": "on" if zid in self._desired_on else "off",
                "actuator_mismatch": actual is not None and actual != (zid in self._desired_on),
                "plant_flow_hold": zid in self._plant_hold_zones or zid in self._handover_hold_zones,
                "plant_flow_hold_reason": ("handover" if zid in self._handover_hold_zones else
                                           "stopping" if zid in self._plant_hold_zones else None),
                "blocked_by": block_reasons[0] if block_reasons else None,
                "last_block_reasons": block_reasons,
                "requested_fraction": round(float(z.get("requested_p", 0.0)), 4),
                "requested_t_on_s": round(float(z.get("requested_t_on", 0.0)), 1),
                "scheduled_t_on_s": round(float(slot.get("t_on", z.get("scheduled_t_on", 0.0) or 0.0)), 1),
                "start_offset_s": slot.get("start_off", z.get("start_offset")),
                "arbitration_rank": slot.get("rank", z.get("arbitration_rank")),
                "plant_state": self._plant_state,
                "plant_mode": self._plant_mode,
                "aggregated_demand_ratio": round(demand_ratio, 4),
            }
            if sampled or self._last_zone_diagnostics.get(zid) != payload:
                self._last_zone_diagnostics[zid] = deepcopy(payload)
                listener = self._zone_listeners.get(zid)
                if listener:
                    listener(payload, sampled=sampled)

    async def _start_cycle(self, wants: Dict[str, Dict[str, float]]):
        """Replace the plan atomically; continuous slots keep their actuators open."""
        now_ts = time.time()
        old_end = self._cycle_start + self._cycle_length
        continuous = {
            zid for zid, slot in self._slots.items()
            if zid in wants and self._cycle_start + slot["start_off"] + slot["t_on"] >= old_end
        } if self._cycle_active else set()
        continuous.update(zid for zid in self._zones
                          if now_ts < self._zone_last_on_at.get(zid, 0) + self._minimum_on(zid))
        # Recover a missed slot end before calculating any new restart eligibility.
        for zid in self._zones:
            if self._actuator_state(zid) is True and zid not in continuous and zid not in self._plant_hold_zones:
                # Reconcile after building the new plan so an active source can
                # transfer to a replacement path before this one is closed.
                if self._plant_state == "off" or self._hard_blocked(zid):
                    await self._command_zone(zid, False)
        self._cycle_length = self._compute_cycle_length(list(self._zones.values()))
        self._packing = self._options.get(CONF_PACKING_MODE, DEFAULTS[CONF_PACKING_MODE])
        self._cycle_active = True
        self._cycle_mode = co_mode_from_entity(self.hass, self._options)
        self._cycle_start = now_ts
        self._slots = self._build_slots(wants)

        for zid, slot in self._slots.items():
            z = self._zones.get(zid)
            if not z:
                continue
            z["scheduled_t_on"] = round(slot["t_on"], 1)
            z["start_offset"] = round(slot["start_off"], 1)
            z["arbitration_rank"] = slot["rank"]
            z["coordinator_status"] = "scheduled"

        demand_ratio = self._demand_ratio(wants)
        payload = {
            EVENT_ENTRY_ID: self.entry.entry_id,
            "cycle_id": int(self._cycle_start),
            "mode": co_mode_from_entity(self.hass, self._options),
            "demand_ratio": round(demand_ratio, 3),
            "active_zones": len(self._slots),
            "total_zones": len(self._zones),
            "packing_mode": self._packing,
            "cycle_length_s": self._cycle_length,
        }
        self.hass.bus.async_fire(EVT_HYDRONICS_DEMAND, payload)

        _LOGGER.info(
            "Cycle START: %d zones, demand_ratio=%.2f, cycle_length=%ss, packing=%s",
            len(self._slots),
            demand_ratio,
            self._cycle_length,
            self._packing,
        )

    async def _stop_cycle(self):
        """Discard the plan; retain only valid paths needed for source shutdown."""
        self._cycle_active = False
        self._slots = {}
        await self._reconcile_zones({}, force_off=True)
        if self._plant_state == "off":
            self._cycle_mode = None

    @staticmethod
    def _demand_ratio(wants):
        return sum(w["p"] for w in wants.values()) / len(wants) if wants else 0.0

    def _actuator_state(self, zid: str) -> bool | None:
        entity = (self._zones.get(zid, {}).get("actuator") or {}).get("entity_id")
        state = self.hass.states.get(entity) if entity else None
        if not state or state.state not in ("on", "off"):
            return None
        return state.state == "on"

    def _observe_actuators(self):
        """Track confirmed transitions, including commands made outside this integration."""
        for zid, z in self._zones.items():
            actual = self._actuator_state(zid)
            previous = self._zone_observed.get(zid)
            if actual is not None and actual != previous:
                state = self.hass.states.get(z["actuator"]["entity_id"])
                changed = getattr(state, "last_changed", None)
                at = min(time.time(), changed.timestamp()) if changed else time.time()
                times = self._zone_last_on_at if actual else self._zone_last_off_at
                if zid in self._zone_observed or zid not in times:
                    times[zid] = at
            self._zone_observed[zid] = actual

    def _minimum_on(self, zid):
        z = self._zones[zid]
        return float(z.get("limits", {}).get("zone_min_on_s", 180)) + float(z.get("actuator", {}).get("open_s", 20))

    def _waiting_for_restart(self, zid):
        return (float(self._zones[zid].get("requested_p", 0.0)) > 0 and
                self._actuator_state(zid) is not True and time.time() < self._restart_at(zid))

    def _restart_at(self, zid):
        if self._actuator_state(zid) is True:
            return 0.0
        z = self._zones[zid]
        return self._zone_last_off_at.get(zid, 0.0) + float(z.get("limits", {}).get("zone_min_off_s", 180)) + float(z.get("actuator", {}).get("close_s", 20))

    def _hard_blocked(self, zid):
        z = self._zones[zid]
        reasons = set(z.get("last_block_reasons") or [])
        return bool(z.get("manual_off") or not z.get("eligible_window", True) or
                    reasons - {"no_demand", "zone_min_off", "cycle_capacity"})

    async def _command_zone(self, zid: str, turn_on: bool):
        z = self._zones[zid]
        entity = (z.get("actuator") or {}).get("entity_id")
        actual = self._actuator_state(zid)
        if not entity or actual is turn_on:
            return
        now_ts = time.time()
        if turn_on and (self._hard_blocked(zid) or now_ts < self._restart_at(zid)):
            return
        previous = self._zone_commands.get(zid)
        if previous and previous[0] == turn_on and now_ts - previous[1] < 5:
            return
        self._zone_commands[zid] = (turn_on, now_ts)
        try:
            await self._set_switch_state(entity, turn_on)
        except Exception:
            _LOGGER.exception("Zone %s command failed: requested=%s", zid, "on" if turn_on else "off")
        self._observe_actuators()

    async def _reconcile_zones(self, wants, force_off=False):
        self._plant_hold_zones.intersection_update(
            zid for zid in self._zones if self._actuator_state(zid) is True and not self._hard_blocked(zid)
        )
        desired = set()
        for zid in self._zones:
            if self._hard_blocked(zid):
                self._slots.pop(zid, None)
                self._plant_hold_zones.discard(zid)
                continue
            slot = self._slots.get(zid)
            if zid in wants and self._zone_slot_is_running(zid) and not self._waiting_for_restart(zid):
                desired.add(zid)
            elif not force_off and self._actuator_state(zid) is True and time.time() < self._zone_last_on_at.get(zid, 0) + self._minimum_on(zid):
                desired.add(zid)
            elif slot and zid not in wants:
                self._slots.pop(zid, None)
            if zid in self._plant_hold_zones and self._plant_state == "stopping":
                desired.add(zid)

        await self._retain_handover_path(desired, force_off)
        if self._plant_state == "stopping":
            desired.update(self._plant_hold_zones)
        desired.update(self._handover_hold_zones)
        self._desired_on = desired
        # Submit all openings before any closures, including zero-open-time zones.
        for turn_on in (True, False):
            for zid in self._zones:
                if (zid in desired) is turn_on:
                    await self._command_zone(zid, turn_on)

    def _clear_handover(self):
        self._handover_hold_zones.clear()
        self._handover_deadline = 0.0

    def _zone_is_open(self, zid):
        return (self._actuator_state(zid) is True and not self._hard_blocked(zid)
                and time.time() >= self._zone_last_on_at.get(zid, time.time())
                + float(self._zones[zid].get("actuator", {}).get("open_s", 20)))

    async def _retain_handover_path(self, desired, force_off):
        """Bridge a planned transfer until a confirmed replacement has opened."""
        if force_off or self._plant_state not in ("starting", "running") or not desired:
            self._clear_handover()
            return
        if any(self._zone_is_open(zid) for zid in desired):
            if self._handover_hold_zones:
                _LOGGER.info("Plant handover complete: replacement path open")
            self._clear_handover()
            return
        old_paths = {zid for zid in self._zones if zid not in desired and self._zone_is_open(zid)}
        if not old_paths:
            self._clear_handover()
            return  # A real loss of the last valid path must still stop the source.
        if not self._handover_deadline:
            opening = max(float(self._zones[zid].get("actuator", {}).get("open_s", 20)) for zid in desired)
            self._handover_deadline = time.time() + HANDOVER_CONFIRM_TIMEOUT_SECONDS + opening
            _LOGGER.info("Plant handover waiting: old_zones=%s target_zones=%s",
                         sorted(old_paths), sorted(desired))
        self._handover_hold_zones = old_paths
        if time.time() >= self._handover_deadline:
            _LOGGER.warning("Plant handover timed out; stopping with the existing valid path")
            await self._request_plant_stop("handover_timeout")

    def _flow_zones(self, require_open=False):
        return [zid for zid in self._desired_on
                if self._actuator_state(zid) is True and not self._hard_blocked(zid)
                and (not require_open or self._zone_is_open(zid))]

    def _flow_open_delay(self):
        now_ts = time.time()
        return min((max(0, self._zone_last_on_at.get(zid, now_ts) + float(self._zones[zid].get("actuator", {}).get("open_s", 20)) - now_ts)
                    for zid in self._flow_zones()), default=0)
