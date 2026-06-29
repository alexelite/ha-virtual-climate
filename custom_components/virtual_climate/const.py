DOMAIN = "virtual_climate"

PLATFORMS = ["climate"]  # later: ["climate", "sensor", "switch", "number"]

DATA_KEY_MANAGER = f"{DOMAIN}_manager"
DATA_KEY_ENTRIES = f"{DOMAIN}_entries"

# Global options keys (stored on the config entry)
CONF_GLOBAL_CO_MODE_ENTITY = "global_co_mode_entity"  # e.g. input_boolean / select
CONF_PACKING_MODE = "packing_mode"                    # "simultaneous" | "staggered"
CONF_T_CYCLE_SECONDS = "t_cycle_seconds"              # initial cycle length
CONF_T_CYCLE_MIN = "t_cycle_min"
CONF_T_CYCLE_MAX = "t_cycle_max"
CONF_RH_ALERT = "rh_alert"
CONF_RH_FAULT = "rh_fault"
CONF_DP_SAFETY_MARGIN = "dp_safety_margin_c"
CONF_RH_FAULT_CLEAR_HYST = "rh_fault_clear_hyst"  # hard-coded default; can expose later

# Zone options keys (stored in entry.data["zones"])
CONF_ZONES = "zones"
ZK_ID = "id"
ZK_NAME = "name"
ZK_SENSOR_AIR = "sensor_air"
ZK_SENSOR_FLOOR = "sensor_floor"
ZK_SENSOR_RH = "sensor_rh"
ZK_SWITCH_ACTUATOR = "switch_actuator"
ZK_SUPPORT_MODE = "support_mode"  # "HEAT" | "COOL" | "BOTH"
ZK_FLOOR_LIMITS = "floor_limits"  # dict with heat_min/heat_max/cool_min/cool_max
ZK_OPEN_S = "open_s"
ZK_CLOSE_S = "close_s"
ZK_ZONE_MIN_ON = "zone_min_on_s"
ZK_ZONE_MIN_OFF = "zone_min_off_s"
ZK_WINDOW_SWITCH = "window_switch"

# Bus event names (internal pub/sub)
EVT_ZONE_STATUS = f"{DOMAIN}/zone_status"
EVT_ZONE_SCHEDULE = f"{DOMAIN}/zone_schedule"
EVT_HYDRONICS_DEMAND = f"{DOMAIN}/hydronics_demand"

# Defaults
DEFAULTS = {
    CONF_PACKING_MODE: "simultaneous",
    CONF_T_CYCLE_SECONDS: 12 * 60,
    CONF_T_CYCLE_MIN: 6 * 60,
    CONF_T_CYCLE_MAX: 24 * 60,
    CONF_RH_ALERT: 60.0,
    CONF_RH_FAULT: 70.0,
    CONF_DP_SAFETY_MARGIN: 2.0,
    CONF_RH_FAULT_CLEAR_HYST: 5.0,
}
