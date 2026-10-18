"""Constants for Heat Pump Forecast Optimizer."""

from datetime import timedelta
from typing import Final

DOMAIN: Final = "heatpump_forecast_optimizer"
NAME: Final = "Heat Pump Forecast Optimizer"
VERSION: Final = "0.2.0"

PLATFORMS: Final = ["sensor", "binary_sensor", "switch"]

UPDATE_INTERVAL: Final = timedelta(minutes=15)

CONF_NAME = "name"
CONF_WEATHER_ENTITY = "weather_entity"
CONF_HEATING_OFFSET_ENTITY = "heating_offset_entity"
CONF_DHW_ENTITY = "dhw_entity"
CONF_ROOM_TEMP_ENTITY = "room_temp_entity"

CONF_DAY_START = "day_start"
CONF_DAY_END = "day_end"
CONF_WARM_WINDOW_HOURS = "warm_window_hours"
CONF_FORECAST_HOURS = "forecast_hours"

CONF_BASE_OFFSET = "base_offset"
CONF_MAX_BOOST_STEPS = "max_boost_steps"
CONF_ADVANTAGE_MEDIUM = "advantage_medium"
CONF_ADVANTAGE_STRONG = "advantage_strong"
CONF_ADVANTAGE_MAX = "advantage_max"
CONF_RAMP_HOURS = "ramp_hours"

CONF_ROOM_TARGET = "room_target"
CONF_ROOM_UPPER_MARGIN = "room_upper_margin"
CONF_ROOM_LOWER_MARGIN = "room_lower_margin"

CONF_DHW_NORMAL_TARGET = "dhw_normal_target"
CONF_DHW_REDUCED_TARGET = "dhw_reduced_target"
CONF_DHW_COMFORT_MIN = "dhw_comfort_min"
CONF_DHW_HYGIENE_GUARD = "dhw_hygiene_guard"

CONF_RESTORE_ON_DISABLE = "restore_on_disable"

DEFAULTS: Final = {
    CONF_NAME: "Wärmepumpen Optimierer",
    CONF_DAY_START: "09:00:00",
    CONF_DAY_END: "18:00:00",
    CONF_WARM_WINDOW_HOURS: 3,
    CONF_FORECAST_HOURS: 36,
    CONF_BASE_OFFSET: -4,
    CONF_MAX_BOOST_STEPS: 3,
    CONF_ADVANTAGE_MEDIUM: 3.0,
    CONF_ADVANTAGE_STRONG: 6.0,
    CONF_ADVANTAGE_MAX: 9.0,
    CONF_RAMP_HOURS: 1,
    CONF_ROOM_TARGET: 21.0,
    CONF_ROOM_UPPER_MARGIN: 0.5,
    CONF_ROOM_LOWER_MARGIN: 0.5,
    CONF_DHW_NORMAL_TARGET: 50.0,
    CONF_DHW_REDUCED_TARGET: 45.0,
    CONF_DHW_COMFORT_MIN: 43.0,
    CONF_DHW_HYGIENE_GUARD: 55.0,
    CONF_RESTORE_ON_DISABLE: True,
}
