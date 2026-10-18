"""Data models for Heat Pump Forecast Optimizer."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class OptimizerData:
    """Calculated optimizer state."""

    status: str
    forecast_temperature: float | None
    forecast_min_temperature: float | None
    forecast_max_temperature: float | None
    warm_window_start: datetime | None
    warm_window_end: datetime | None
    warm_window_temperature: float | None
    next_night_minimum: float | None
    temperature_advantage: float | None
    boost_active: bool
    ramp_active: bool
    room_temperature: float | None
    planned_offset: float | None
    dhw_current_temperature: float | None
    dhw_planned_target: float | None
    dhw_comfort_fallback: bool
    dhw_hygiene_guard_active: bool
