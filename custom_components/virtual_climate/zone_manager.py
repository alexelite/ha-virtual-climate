from __future__ import annotations

import asyncio
import logging, time
from datetime import timedelta
from typing import Callable, Dict, Any, List, Optional
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval, async_call_later
from homeassistant.const import SERVICE_TURN_ON, SERVICE_TURN_OFF
from homeassistant.core import DOMAIN as HA_DOMAIN

from .const import (
    DOMAIN, EVT_ZONE_STATUS, EVT_ZONE_SCHEDULE, EVT_HYDRONICS_DEMAND,
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

_LOGGER = logging.getLogger(__name__)

GLOBAL_DEMAND_RATIO_PRECISION = 2
GLOBAL_DEMAND_RATIO_MIN_DELTA = 0.02

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
        self._cycle_length = int(self._options.get(CONF_T_CYCLE_SECONDS, DEFAULTS[CONF_T_CYCLE_SECONDS]))
        self._slots: Dict[str, Dict[str, float]] = {}  # zone_id -> {start_offset, t_on}
        self._zone_last_on_at: Dict[str, float] = {}
        self._zone_last_off_at: Dict[str, float] = {}
        self._plant_state = "off"  # off | starting | running | stopping
        self._plant_mode: Optional[str] = None
        self._plant_started_at = 0.0
        self._plant_stopped_at = 0.0
        self._plant_session = 0
        self._plant_start_task: Optional[asyncio.Task] = None
        self._plant_stop_task: Optional[asyncio.Task] = None
        self._global_diag: Dict[str, Any] = {}
        self._listeners: list[Callable[[], None]] = []

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
        self._unsub_bus = self.hass.bus.async_listen(EVT_ZONE_STATUS, self._on_zone_status)
        self._unsub_tick = async_track_time_interval(self.hass, self._on_tick, timedelta(seconds=1))
        self._refresh_global_diagnostics(system_mode=co_mode_from_entity(self.hass, self._options), phase="startup")
        _LOGGER.info("ZoneManager started: t_cycle=%ss, packing=%s", self._t_cycle, self._packing)

    async def async_stop(self):
        """Stop timers and listeners."""
        if self._unsub_bus:
            self._unsub_bus()
            self._unsub_bus = None
        if self._unsub_tick:
            self._unsub_tick()
            self._unsub_tick = None
        self._cancel_task(self._plant_start_task)
        self._cancel_task(self._plant_stop_task)
        self._plant_start_task = None
        self._plant_stop_task = None
        await self._set_switch_state(self._options.get(CONF_HEATING_SOURCE_ENTITY), False)
        await self._set_switch_state(self._options.get(CONF_COOLING_SOURCE_ENTITY), False)
        await self._set_switch_state(self._options.get(CONF_CIRCULATION_PUMP_ENTITY), False)
        self._cycle_active = False
        self._slots = {}
        self._plant_state = "off"
        self._plant_mode = None
        self._refresh_global_diagnostics(system_mode=co_mode_from_entity(self.hass, self._options), phase="stopped")
        _LOGGER.info("ZoneManager stopped")

    @callback
    def _on_zone_status(self, event):
        data: dict = event.data or {}
        if data.get(EVENT_ENTRY_ID) != self.entry.entry_id:
            return
        zid = data.get("zone_id")
        if not zid:
            return
        data.setdefault("last_block_reasons", [])
        self._zones[zid] = data

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
        now_ts = time.time()
        scheduled_zones = sum(1 for z in zone_states if z.get("zone_id") in self._slots)
        running_zones = sum(
            1 for z in zone_states
            if self._zone_slot_is_running(z.get("zone_id"), now_ts)
        )
        blocked_zones = sum(1 for z in zone_states if z.get("coordinator_status") == "blocked")
        previous_ratio = float(self._global_diag.get("aggregated_demand_ratio", 0.0) or 0.0)
        rounded_ratio = round(float(demand_ratio), GLOBAL_DEMAND_RATIO_PRECISION)
        if abs(rounded_ratio - previous_ratio) < GLOBAL_DEMAND_RATIO_MIN_DELTA:
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
            "blocked_zones": blocked_zones,
        }
        for listener in list(self._listeners):
            listener()

    async def _on_tick(self, now):
        """Cycle state machine (PLAN → START/RUN → STOP). Runs every second."""
        self._options = get_current_config(self.entry)
        system_mode = co_mode_from_entity(self.hass, self._options)
        if system_mode == "OFF":
            if self._cycle_active:
                await self._stop_cycle()
            self._publish_zone_diagnostics(None, system_mode, "global_off")
            await self._request_plant_stop("global_off")
            return

        if self._plant_mode and self._plant_mode != system_mode and self._plant_state in ("starting", "running"):
            if self._cycle_active:
                await self._stop_cycle()
            self._publish_zone_diagnostics(None, system_mode, "mode_change")
            await self._request_plant_stop("mode_change")
            return

        plan = self._plan_cycle()
        if not self._cycle_active:
            # PLAN: decide if we need to run a cycle
            if plan:
                await self._request_plant_start(system_mode, plan)
                await self._start_cycle(plan)
            else:
                self._publish_zone_diagnostics(None, system_mode, "idle")
                await self._request_plant_stop("no_demand")
        else:
            # Check if cycle should end
            elapsed = time.time() - self._cycle_start
            if elapsed >= self._cycle_length:
                await self._stop_cycle()
                if not plan:
                    self._publish_zone_diagnostics(None, system_mode, "idle")
                    await self._request_plant_stop("cycle_end_no_demand")
                else:
                    await self._request_plant_start(system_mode, plan)
                    await self._start_cycle(plan)
            else:
                self._publish_zone_diagnostics(plan, system_mode, "running")

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
        cycle_length = self._compute_cycle_length(zones)
        self._cycle_length = cycle_length

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
                surface = t_floor if (t_floor is not None) else (t_air if t_air is not None else None)
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

            zone_min_off = float(limits.get("zone_min_off_s", 180))
            close_s = float(z.get("actuator", {}).get("close_s", 20))
            last_off_at = self._zone_last_off_at.get(zid)
            if last_off_at is not None:
                min_restart_at = last_off_at + zone_min_off + close_s
                if time.time() < min_restart_at:
                    block_reasons.append("zone_min_off")
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
            return min_cycle

        supported = [
            z for z in zones
            if not z.get("manual_off")
            and z.get("eligible_window", True)
        ]
        if not supported:
            return max(min_cycle, min(max_cycle, base_cycle))

        demand_values: List[float] = []
        for z in supported:
            delta = z.get("delta_air")
            mode = z.get("active_co_mode") or z.get("co_mode") or "HEAT"
            if delta is None:
                continue
            if mode == "HEAT":
                p = max(0.0, min(1.0, float(delta) / 1.5))
            else:
                p = max(0.0, min(1.0, (-float(delta)) / 1.5))
            demand_values.append(p)

        if not demand_values:
            return max(min_cycle, min(max_cycle, base_cycle))

        avg_demand = sum(demand_values) / len(demand_values)
        dynamic_cycle = min_cycle + (max_cycle - min_cycle) * avg_demand
        return int(round(dynamic_cycle))

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
            blocking=False,
        )

    async def _set_changeover_for_mode(self, mode: str) -> None:
        entity_id = self._options.get(CONF_CHANGEOVER_ENTITY)
        if not entity_id:
            return
        # Assumption for MVP: ON selects COOL, OFF selects HEAT.
        await self._set_switch_state(entity_id, mode == "COOL")

    async def _set_target_supply_for_mode(self, mode: str) -> None:
        entity_id = self._options.get(CONF_TARGET_SUPPLY_TEMPERATURE_ENTITY)
        if not entity_id:
            return

        target = float(
            self._options.get(
                CONF_COOLING_SUPPLY_TARGET if mode == "COOL" else CONF_HEATING_SUPPLY_TARGET,
                DEFAULTS[CONF_COOLING_SUPPLY_TARGET if mode == "COOL" else CONF_HEATING_SUPPLY_TARGET],
            )
        )
        domain = entity_id.split(".", 1)[0]
        await self.hass.services.async_call(
            domain,
            "set_value",
            {"entity_id": entity_id, "value": target},
            blocking=False,
        )

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

        if self._plant_stop_task and not self._plant_stop_task.done():
            self._cancel_task(self._plant_stop_task)
            self._plant_stop_task = None

        if self._plant_state in ("running", "starting") and self._plant_mode != mode:
            await self._request_plant_stop("mode_change")
            return

        self._plant_start_task = self.hass.async_create_task(
            self._async_start_plant(mode, demand_ratio)
        )

    async def _request_plant_stop(self, reason: str) -> None:
        if not self._plant_control_enabled():
            return
        if self._plant_state == "off":
            return
        if self._plant_stop_task and not self._plant_stop_task.done():
            return

        self._cancel_task(self._plant_start_task)
        self._plant_start_task = None
        self._plant_stop_task = self.hass.async_create_task(
            self._async_stop_plant(reason)
        )

    async def _async_start_plant(self, mode: str, demand_ratio: float) -> None:
        self._plant_session += 1
        session = self._plant_session
        self._plant_state = "starting"
        self._plant_mode = mode
        self._refresh_global_diagnostics(demand_ratio=demand_ratio, system_mode=mode, phase="plant_start")
        _LOGGER.info(
            "Plant START requested: session=%s mode=%s demand_ratio=%.2f",
            session,
            mode,
            demand_ratio,
        )
        try:
            min_off = int(self._options.get(CONF_MINIMUM_OFF_TIME_SECONDS, DEFAULTS[CONF_MINIMUM_OFF_TIME_SECONDS]))
            if self._plant_stopped_at and min_off > 0:
                wait_off = max(0.0, (self._plant_stopped_at + min_off) - time.time())
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
            await self._set_switch_state(self._options.get(CONF_CIRCULATION_PUMP_ENTITY), True)

            additional_source_delay = max(0, source_delay - pump_delay)
            if additional_source_delay > 0:
                _LOGGER.info("Plant additional delay before %s source: %ss", mode, additional_source_delay)
                await asyncio.sleep(additional_source_delay)

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
            self._refresh_global_diagnostics(demand_ratio=demand_ratio, system_mode=mode, phase="plant_running")
            _LOGGER.info("Plant START complete: session=%s mode=%s", session, mode)
        except asyncio.CancelledError:
            _LOGGER.debug("Plant START cancelled: session=%s", session)
            raise
        finally:
            self._plant_start_task = None

    async def _async_stop_plant(self, reason: str) -> None:
        self._plant_state = "stopping"
        mode = self._plant_mode or "HEAT"
        self._refresh_global_diagnostics(system_mode=mode, phase=f"plant_stop:{reason}")
        _LOGGER.info("Plant STOP requested: mode=%s reason=%s", mode, reason)
        try:
            min_run = int(self._options.get(CONF_MINIMUM_RUN_TIME_SECONDS, DEFAULTS[CONF_MINIMUM_RUN_TIME_SECONDS]))
            if self._plant_started_at and min_run > 0:
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
            if post_run > 0 and self._options.get(CONF_CIRCULATION_PUMP_ENTITY):
                _LOGGER.info("Plant pump post-run: %ss", post_run)
                await asyncio.sleep(post_run)

            await self._set_switch_state(self._options.get(CONF_CIRCULATION_PUMP_ENTITY), False)

            self._plant_state = "off"
            self._plant_stopped_at = time.time()
            previous_mode = self._plant_mode
            self._plant_mode = None
            self._plant_started_at = 0.0
            self._refresh_global_diagnostics(system_mode=co_mode_from_entity(self.hass, self._options), phase=f"plant_off:{reason}")
            _LOGGER.info("Plant STOP complete: previous_mode=%s reason=%s", previous_mode, reason)
        except asyncio.CancelledError:
            _LOGGER.debug("Plant STOP cancelled")
            raise
        finally:
            self._plant_stop_task = None

    def _build_slots(self, wants: Dict[str, Dict[str, float]]) -> Dict[str, Dict[str, float]]:
        ordered = sorted(
            wants.items(),
            key=lambda item: (-item[1]["p"], item[0]),
        )
        slot_count = len(ordered)
        slots: Dict[str, Dict[str, float]] = {}

        if self._packing == "staggered" and slot_count > 1:
            spacing = self._cycle_length / slot_count
            for index, (zid, w) in enumerate(ordered):
                start_off = round(index * spacing, 1)
                t_on = min(float(w["t_on"]), max(0.0, self._cycle_length - start_off))
                slots[zid] = {"start_off": start_off, "t_on": round(t_on, 1), "rank": index + 1}
        else:
            for index, (zid, w) in enumerate(ordered):
                slots[zid] = {"start_off": 0.0, "t_on": round(float(w["t_on"]), 1), "rank": index + 1}

        return slots

    def _publish_zone_diagnostics(self, wants: Optional[Dict[str, Dict[str, float]]], system_mode: str, phase: str) -> None:
        demand_ratio = 0.0
        if wants:
            demand_ratio = sum(w["p"] for w in wants.values()) / max(1, len(wants))
        self._refresh_global_diagnostics(demand_ratio=demand_ratio, system_mode=system_mode, phase=phase)

        now_ts = time.time()
        for zid, z in self._zones.items():
            slot = self._slots.get(zid, {})
            block_reasons = list(z.get("last_block_reasons") or [])
            scheduled = zid in self._slots
            zone_status = z.get("coordinator_status", "idle")
            is_running = self._zone_slot_is_running(zid, now_ts)
            if is_running:
                coordinator_status = "running"
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
            self.hass.bus.async_fire(EVT_ZONE_SCHEDULE, payload)

    async def _start_cycle(self, wants: Dict[str, Dict[str, float]]):
        """Start the cycle, schedule actuators, and publish hydronics demand."""
        self._cycle_active = True
        self._cycle_start = time.time()
        self._slots = self._build_slots(wants)
        system_mode = co_mode_from_entity(self.hass, self._options)

        for zid, slot in self._slots.items():
            z = self._zones.get(zid)
            if not z:
                continue
            z["scheduled_t_on"] = round(slot["t_on"], 1)
            z["start_offset"] = round(slot["start_off"], 1)
            z["arbitration_rank"] = slot["rank"]
            z["coordinator_status"] = "scheduled"

        # Turn on all zones with open delay, and start source warmup if you add it later
        for zid, slot in self._slots.items():
            z = self._zones.get(zid, {})
            act = z.get("actuator", {})
            ent = act.get("entity_id")
            delay = float(slot.get("start_off", 0.0))
            if ent and delay <= 0:
                await self.hass.services.async_call(HA_DOMAIN, SERVICE_TURN_ON, {"entity_id": ent}, blocking=False)
                self._zone_last_on_at[zid] = time.time()
                z["coordinator_status"] = "running"
            elif ent:
                async_call_later(self.hass, delay, lambda *_ , zone_id=zid: self.hass.async_create_task(self._turn_on_zone(zone_id)))

        # Hydronics demand (basic)
        demand_ratio = 0.0
        if wants:
            demand_ratio = sum(w["p"] for w in wants.values()) / max(1, len(wants))
        payload = {
            EVENT_ENTRY_ID: self.entry.entry_id,
            "cycle_id": int(self._cycle_start),
            "mode": system_mode,
            "demand_ratio": round(demand_ratio, 3),
            "active_zones": len(self._slots),
            "total_zones": len(self._zones),
            "packing_mode": self._packing,
            "cycle_length_s": self._cycle_length,
        }
        self.hass.bus.async_fire(EVT_HYDRONICS_DEMAND, payload)

        self._publish_zone_diagnostics(wants, system_mode, "start")
        _LOGGER.info(
            "Cycle START: %d zones, demand_ratio=%.2f, cycle_length=%ss, packing=%s",
            len(self._slots),
            demand_ratio,
            self._cycle_length,
            self._packing,
        )

        # Schedule per-zone turn-off at end of each t_on
        for zid, slot in self._slots.items():
            when = self._cycle_start + slot["start_off"] + slot["t_on"]
            delay = max(0.0, when - time.time())
            async_call_later(self.hass, delay, lambda *_ , zone_id=zid: self.hass.async_create_task(self._turn_off_zone(zone_id)))

    async def _turn_on_zone(self, zid: str):
        z = self._zones.get(zid, {})
        act = z.get("actuator", {})
        ent = act.get("entity_id")
        if ent and self._cycle_active:
            await self.hass.services.async_call(HA_DOMAIN, SERVICE_TURN_ON, {"entity_id": ent}, blocking=False)
            self._zone_last_on_at[zid] = time.time()
            z["coordinator_status"] = "running"
            self._publish_zone_diagnostics(None, co_mode_from_entity(self.hass, self._options), "running")

    async def _turn_off_zone(self, zid: str):
        z = self._zones.get(zid, {})
        act = z.get("actuator", {})
        ent = act.get("entity_id")
        if ent:
            await self.hass.services.async_call(HA_DOMAIN, SERVICE_TURN_OFF, {"entity_id": ent}, blocking=False)
            self._zone_last_off_at[zid] = time.time()
            z["coordinator_status"] = "completed"
            self._publish_zone_diagnostics(None, co_mode_from_entity(self.hass, self._options), "running")

    async def _stop_cycle(self):
        """Stop the cycle and ensure all zones are off."""
        self._cycle_active = False
        # Safety: ensure all actuators OFF
        for zid, z in self._zones.items():
            ent = (z.get("actuator") or {}).get("entity_id")
            if ent:
                await self.hass.services.async_call(HA_DOMAIN, SERVICE_TURN_OFF, {"entity_id": ent}, blocking=False)
                self._zone_last_off_at[zid] = time.time()
            z["coordinator_status"] = "idle"
        self._slots = {}
        self._publish_zone_diagnostics(None, co_mode_from_entity(self.hass, self._options), "stop")
        _LOGGER.info("Cycle STOP")
