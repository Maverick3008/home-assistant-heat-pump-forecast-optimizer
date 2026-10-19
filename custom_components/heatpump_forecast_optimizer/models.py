"""Data models for Heat Pump Forecast Optimizer."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


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
    warm_window_active: bool
    ramp_active: bool
    room_temperature: float | None
    planned_offset: float | None
    dhw_current_temperature: float | None
    dhw_planned_target: float | None
    dhw_comfort_fallback: bool
    dhw_hygiene_guard_active: bool

    # v0.2.1 planning / diagnostics
    plan_generated_at: datetime | None = None
    heating_plan: list[dict[str, Any]] = field(default_factory=list)
    dhw_plan: list[dict[str, Any]] = field(default_factory=list)
    next_change: datetime | None = None
    next_change_summary: str | None = None
    next_offset: float | None = None
    next_dhw_target: float | None = None
    last_write: datetime | None = None
    last_offset_written: float | None = None
    last_dhw_written: float | None = None
