"""Coordinator for Heat Pump Forecast Optimizer."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
import logging
from statistics import mean
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ADVANTAGE_MAX,
    CONF_ADVANTAGE_MEDIUM,
    CONF_ADVANTAGE_STRONG,
    CONF_BASE_OFFSET,
    CONF_DAY_END,
    CONF_DAY_START,
    CONF_DHW_COMFORT_MIN,
    CONF_DHW_ENTITY,
    CONF_DHW_HYGIENE_GUARD,
    CONF_DHW_NORMAL_TARGET,
    CONF_DHW_REDUCED_TARGET,
    CONF_FORECAST_HOURS,
    CONF_HEATING_OFFSET_ENTITY,
    CONF_MAX_BOOST_STEPS,
    CONF_RAMP_HOURS,
    CONF_RESTORE_ON_DISABLE,
    CONF_ROOM_LOWER_MARGIN,
    CONF_ROOM_TARGET,
    CONF_ROOM_TEMP_ENTITY,
    CONF_ROOM_UPPER_MARGIN,
    CONF_WARM_WINDOW_HOURS,
    CONF_WEATHER_ENTITY,
    DEFAULTS,
    DOMAIN,
    UPDATE_INTERVAL,
)
from .models import OptimizerData

_LOGGER = logging.getLogger(__name__)
# Keep the existing storage version: the new diagnostic keys are optional and
# backwards-compatible with v0.2.0.
STORAGE_VERSION = 1


@dataclass(slots=True)
class ForecastPoint:
    """Normalized hourly forecast point."""

    dt: datetime
    temperature: float


@dataclass(slots=True)
class WarmWindow:
    """One optimized daytime block and its following-night context."""

    start: datetime
    end: datetime
    mean_temperature: float
    night_minimum: float | None
    advantage: float | None


class HeatPumpForecastCoordinator(DataUpdateCoordinator[OptimizerData]):
    """Calculate and apply forecast-based heat-pump targets."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        config: dict[str, Any],
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.entry = entry
        self.config = config
        self.enabled = False
        self.last_write: datetime | None = None
        self.last_offset_written: float | None = None
        self.last_dhw_written: float | None = None
        self._store: Store[dict[str, Any]] = Store(
            hass,
            STORAGE_VERSION,
            f"{DOMAIN}.{entry.entry_id}",
        )

    async def _async_setup(self) -> None:
        """Restore persistent runtime state."""
        stored = await self._store.async_load()
        if not isinstance(stored, dict):
            return

        self.enabled = bool(stored.get("enabled", False))
        self.last_offset_written = self._as_float(stored.get("last_offset_written"))
        self.last_dhw_written = self._as_float(stored.get("last_dhw_written"))

        raw_last_write = stored.get("last_write")
        if raw_last_write:
            parsed = dt_util.parse_datetime(str(raw_last_write))
            if parsed is not None:
                self.last_write = dt_util.as_local(parsed)

    async def _async_save_runtime(self) -> None:
        """Persist master-switch and successful-write diagnostics."""
        await self._store.async_save(
            {
                "enabled": self.enabled,
                "last_write": self.last_write.isoformat() if self.last_write else None,
                "last_offset_written": self.last_offset_written,
                "last_dhw_written": self.last_dhw_written,
            }
        )

    def _cfg(self, key: str) -> Any:
        """Read merged config/options with a default fallback."""
        return self.config.get(key, DEFAULTS.get(key))

    @staticmethod
    def _as_float(value: Any) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _parse_time(value: Any) -> time:
        """Normalize selector/string time values."""
        if isinstance(value, time):
            return value
        text = str(value or "00:00:00")
        try:
            return time.fromisoformat(text)
        except ValueError:
            return time(0, 0)

    @staticmethod
    def _time_in_window(value: time, start: time, end: time) -> bool:
        """Return whether a local time is in a possibly overnight window."""
        if start <= end:
            return start <= value < end
        return value >= start or value < end

    @staticmethod
    def _read_state_number(hass: HomeAssistant, entity_id: str | None) -> float | None:
        """Read a numerical state."""
        if not entity_id:
            return None
        state = hass.states.get(entity_id)
        if state is None or state.state in ("unknown", "unavailable", "none", ""):
            return None
        try:
            return float(state.state)
        except (TypeError, ValueError):
            return None

    def _climate_target(self) -> float | None:
        """Return the current target from the configured climate offset entity."""
        entity_id = self._cfg(CONF_HEATING_OFFSET_ENTITY)
        state = self.hass.states.get(entity_id) if entity_id else None
        if state is None:
            return None
        return self._as_float(state.attributes.get("temperature"))

    def _dhw_values(self) -> tuple[float | None, float | None, str | None]:
        """Return current DHW temperature, target and operation mode."""
        entity_id = self._cfg(CONF_DHW_ENTITY)
        state = self.hass.states.get(entity_id) if entity_id else None
        if state is None:
            return None, None, None

        return (
            self._as_float(state.attributes.get("current_temperature")),
            self._as_float(state.attributes.get("temperature")),
            state.attributes.get("operation_mode"),
        )

    async def _get_hourly_forecast(self) -> list[ForecastPoint]:
        """Get the hourly weather forecast through Home Assistant."""
        weather_entity = self._cfg(CONF_WEATHER_ENTITY)
        if not weather_entity:
            raise HomeAssistantError("Keine Wetter-Entität konfiguriert")

        response = await self.hass.services.async_call(
            "weather",
            "get_forecasts",
            {ATTR_ENTITY_ID: weather_entity, "type": "hourly"},
            blocking=True,
            return_response=True,
        )

        if not isinstance(response, dict):
            raise HomeAssistantError("Wetterdienst lieferte keine Antwort")

        raw = response.get(weather_entity, {})
        forecasts = raw.get("forecast", []) if isinstance(raw, dict) else []

        now = dt_util.now()
        # Keep the visible plan horizon configurable, but fetch at least 48 h
        # so tomorrow's warm period can be compared with the *following* night.
        horizon = now + timedelta(
            hours=max(48, int(self._cfg(CONF_FORECAST_HOURS)))
        )
        points: list[ForecastPoint] = []

        for item in forecasts:
            if not isinstance(item, dict):
                continue
            raw_dt = item.get("datetime")
            raw_temp = item.get("temperature")
            if raw_dt is None or raw_temp is None:
                continue

            point_dt = dt_util.parse_datetime(str(raw_dt))
            if point_dt is None:
                continue
            temperature = self._as_float(raw_temp)
            if temperature is None:
                continue

            point_dt = dt_util.as_local(point_dt)
            if now - timedelta(hours=2) <= point_dt <= horizon:
                points.append(ForecastPoint(point_dt, temperature))

        points.sort(key=lambda item: item.dt)
        if not points:
            raise HomeAssistantError(
                "Die Wetter-Entität liefert keine stündlichen Temperaturwerte"
            )
        return points

    @staticmethod
    def _closest_temperature(
        points: list[ForecastPoint],
        now: datetime,
    ) -> float | None:
        """Return forecast temperature nearest to now."""
        if not points:
            return None
        return min(
            points,
            key=lambda point: abs((point.dt - now).total_seconds()),
        ).temperature

    def _find_night_minimum(
        self,
        points: list[ForecastPoint],
        warm_end: datetime,
    ) -> float | None:
        """Find the minimum forecast temperature after one warm block."""
        day_start = self._parse_time(self._cfg(CONF_DAY_START))
        day_end = self._parse_time(self._cfg(CONF_DAY_END))
        limit = warm_end + timedelta(hours=16)

        # A partial evening is not a reliable "night minimum". Require
        # forecast coverage until roughly 06:00 for a 16:00 window end.
        required_coverage = warm_end + timedelta(hours=14)
        if not any(point.dt >= required_coverage for point in points):
            return None

        candidates = [
            point.temperature
            for point in points
            if warm_end <= point.dt <= limit
            and not self._time_in_window(point.dt.time(), day_start, day_end)
        ]
        return min(candidates) if candidates else None

    def _find_warm_windows(
        self,
        points: list[ForecastPoint],
        now: datetime,
    ) -> list[WarmWindow]:
        """Find the best remaining warm block for each local forecast day.

        v0.2.0 chose one globally warmest block across the whole horizon. That
        could skip today's useful warm period merely because tomorrow is warmer.
        v0.2.1 therefore optimizes each forecast day independently.
        """
        day_start = self._parse_time(self._cfg(CONF_DAY_START))
        day_end = self._parse_time(self._cfg(CONF_DAY_END))
        hours = max(1, int(self._cfg(CONF_WARM_WINDOW_HOURS)))
        windows: list[WarmWindow] = []

        dates = sorted({point.dt.date() for point in points})
        for local_date in dates:
            day_points = [
                point
                for point in points
                if point.dt.date() == local_date
                and self._time_in_window(point.dt.time(), day_start, day_end)
            ]
            if len(day_points) < hours:
                continue

            best: tuple[datetime, datetime, float] | None = None
            for index in range(0, len(day_points) - hours + 1):
                chunk = day_points[index : index + hours]
                contiguous = all(
                    timedelta(minutes=45)
                    <= chunk[pos + 1].dt - chunk[pos].dt
                    <= timedelta(minutes=75)
                    for pos in range(len(chunk) - 1)
                )
                if not contiguous:
                    continue

                window_end = chunk[-1].dt + timedelta(hours=1)
                if window_end <= now:
                    continue

                average = mean(point.temperature for point in chunk)
                candidate = (chunk[0].dt, window_end, average)
                if best is None or average > best[2]:
                    best = candidate

            if best is None:
                continue

            night_min = self._find_night_minimum(points, best[1])
            advantage = best[2] - night_min if night_min is not None else None
            windows.append(
                WarmWindow(
                    start=best[0],
                    end=best[1],
                    mean_temperature=best[2],
                    night_minimum=night_min,
                    advantage=advantage,
                )
            )

        windows.sort(key=lambda item: item.start)
        return windows

    def _boost_steps(self, advantage: float | None) -> int:
        """Map temperature advantage to conservative offset steps."""
        if advantage is None or advantage < float(self._cfg(CONF_ADVANTAGE_MEDIUM)):
            return 0
        if advantage < float(self._cfg(CONF_ADVANTAGE_STRONG)):
            return 1
        if advantage < float(self._cfg(CONF_ADVANTAGE_MAX)):
            return 2
        return max(0, int(self._cfg(CONF_MAX_BOOST_STEPS)))

    def _room_temperature(self) -> float | None:
        """Return optional room temperature sensor state."""
        return self._read_state_number(self.hass, self._cfg(CONF_ROOM_TEMP_ENTITY))

    def _nominal_offset_at(
        self,
        when: datetime,
        windows: list[WarmWindow],
    ) -> tuple[float, str, int, WarmWindow | None]:
        """Calculate the forecast-only offset target for one point in time."""
        base = float(self._cfg(CONF_BASE_OFFSET))
        max_steps = max(0, int(self._cfg(CONF_MAX_BOOST_STEPS)))
        ramp_hours = max(0, int(self._cfg(CONF_RAMP_HOURS)))

        for window in windows:
            steps = min(self._boost_steps(window.advantage), max_steps)
            if window.start <= when < window.end:
                return base + steps, "optimales_zeitfenster", steps, window
            if (
                ramp_hours > 0
                and window.start - timedelta(hours=ramp_hours) <= when < window.start
            ):
                applied = max(0, steps - 1) if steps > 1 else steps
                return base + applied, "rampe_vorher", applied, window
            if (
                ramp_hours > 0
                and window.end <= when < window.end + timedelta(hours=ramp_hours)
            ):
                applied = max(0, steps - 1)
                return base + applied, "rampe_nachher", applied, window

        return base, "basis", 0, None

    def _calculate_offset(
        self,
        *,
        now: datetime,
        windows: list[WarmWindow],
        room_temperature: float | None,
    ) -> tuple[float, bool, bool, int]:
        """Calculate the current effective offset including the room guard."""
        nominal, phase, applied_steps, _window = self._nominal_offset_at(now, windows)
        base = float(self._cfg(CONF_BASE_OFFSET))
        max_steps = max(0, int(self._cfg(CONF_MAX_BOOST_STEPS)))
        original_steps = applied_steps

        boost_active = phase == "optimales_zeitfenster" and applied_steps > 0
        ramp_active = phase.startswith("rampe_") and applied_steps > 0

        if room_temperature is not None:
            target = float(self._cfg(CONF_ROOM_TARGET))
            upper = float(self._cfg(CONF_ROOM_UPPER_MARGIN))
            lower = float(self._cfg(CONF_ROOM_LOWER_MARGIN))

            # Suppress forecast pre-heating if the building is already warm.
            if room_temperature >= target + upper and applied_steps > 0:
                nominal = base
                boost_active = False
                ramp_active = False
            # If the building is already below the desired band, permit one step
            # in the selected warm/ramp window even when forecast advantage alone
            # would not have requested a boost.
            elif (
                room_temperature <= target - lower
                and phase != "basis"
                and max_steps > 0
                and applied_steps == 0
            ):
                nominal = base + 1
                boost_active = phase == "optimales_zeitfenster"
                ramp_active = phase.startswith("rampe_")

        return nominal, boost_active, ramp_active, original_steps

    @staticmethod
    def _window_active(when: datetime, windows: list[WarmWindow]) -> bool:
        return any(window.start <= when < window.end for window in windows)

    def _build_plans(
        self,
        points: list[ForecastPoint],
        *,
        now: datetime,
        windows: list[WarmWindow],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Build future heating and DHW curves for dashboard visualization.

        The heating plan is the nominal weather plan. Future room temperature
        cannot be predicted reliably, so the room guard is evaluated live when
        each target is due. DHW comfort/hygiene guards are also live overrides.
        """
        heating: list[dict[str, Any]] = []
        dhw: list[dict[str, Any]] = []
        normal_dhw = float(self._cfg(CONF_DHW_NORMAL_TARGET))
        reduced_dhw = float(self._cfg(CONF_DHW_REDUCED_TARGET))
        room_guard_configured = bool(self._cfg(CONF_ROOM_TEMP_ENTITY))

        plan_end = now + timedelta(hours=int(self._cfg(CONF_FORECAST_HOURS)))
        future_points = [
            point
            for point in points
            if now - timedelta(minutes=5) <= point.dt <= plan_end
        ]
        if not future_points:
            return heating, dhw

        chart_points: list[ForecastPoint] = []
        first = future_points[0]
        if first.dt > now + timedelta(minutes=5):
            chart_points.append(
                ForecastPoint(
                    now,
                    self._closest_temperature(points, now) or first.temperature,
                )
            )
        chart_points.extend(future_points)

        for point in chart_points:
            offset, phase, steps, window = self._nominal_offset_at(point.dt, windows)
            heating_item: dict[str, Any] = {
                "datetime": point.dt.isoformat(),
                "offset": round(offset, 1),
                "outdoor_temperature": round(point.temperature, 1),
                "phase": phase,
                "boost_steps": steps,
            }
            if window is not None and window.advantage is not None:
                heating_item["temperature_advantage"] = round(window.advantage, 2)
            if room_guard_configured and steps > 0:
                heating_item["conditional_room_guard"] = True
            heating.append(heating_item)

            in_warm_window = self._window_active(point.dt, windows)
            dhw.append(
                {
                    "datetime": point.dt.isoformat(),
                    "temperature": normal_dhw if in_warm_window else reduced_dhw,
                    "outdoor_temperature": round(point.temperature, 1),
                    "phase": "optimales_zeitfenster" if in_warm_window else "reduziert",
                }
            )

        return heating, dhw

    @staticmethod
    def _next_plan_change(
        *,
        now: datetime,
        heating_plan: list[dict[str, Any]],
        dhw_plan: list[dict[str, Any]],
        current_nominal_offset: float | None,
        current_nominal_dhw: float | None,
    ) -> tuple[datetime | None, str | None, float | None, float | None]:
        """Find the next nominal schedule change."""
        combined: dict[str, dict[str, Any]] = {}
        for item in heating_plan:
            stamp = str(item["datetime"])
            combined.setdefault(stamp, {})["offset"] = item.get("offset")
            combined[stamp]["heating_conditional"] = item.get(
                "conditional_room_guard", False
            )
        for item in dhw_plan:
            stamp = str(item["datetime"])
            combined.setdefault(stamp, {})["dhw"] = item.get("temperature")

        active_offset = current_nominal_offset
        active_dhw = current_nominal_dhw

        def as_float(value: Any) -> float | None:
            try:
                return float(value)
            except (TypeError, ValueError):
                return None

        ordered: list[tuple[datetime, dict[str, Any]]] = []
        for raw_dt, values in combined.items():
            parsed = dt_util.parse_datetime(raw_dt)
            if parsed is not None:
                ordered.append((dt_util.as_local(parsed), values))
        ordered.sort(key=lambda item: item[0])

        for when, values in ordered:
            if when <= now + timedelta(minutes=1):
                continue

            new_offset = as_float(values.get("offset"))
            new_dhw = as_float(values.get("dhw"))
            if new_offset is None:
                new_offset = active_offset
            if new_dhw is None:
                new_dhw = active_dhw

            offset_changed = (
                new_offset is not None
                and active_offset is not None
                and abs(new_offset - active_offset) >= 0.5
            )
            dhw_changed = (
                new_dhw is not None
                and active_dhw is not None
                and abs(new_dhw - active_dhw) >= 0.5
            )

            if offset_changed or dhw_changed:
                parts: list[str] = []
                if offset_changed:
                    text = f"Heizung {active_offset:g} → {new_offset:g} K"
                    if values.get("heating_conditional"):
                        text += " (Raumtemperatur wird live geprüft)"
                    parts.append(text)
                if dhw_changed:
                    parts.append(f"Warmwasser {active_dhw:g} → {new_dhw:g} °C")
                return when, "; ".join(parts), new_offset, new_dhw

            if new_offset is not None:
                active_offset = new_offset
            if new_dhw is not None:
                active_dhw = new_dhw

        return None, None, None, None

    @staticmethod
    def _round_to_entity_step(state: Any, value: float) -> float:
        """Apply min/max/step attributes exposed by an entity."""
        if state is None:
            return value

        for attr, fn in (("min_temp", max), ("max_temp", min)):
            raw = state.attributes.get(attr)
            try:
                value = fn(value, float(raw))
            except (TypeError, ValueError):
                pass

        try:
            step = float(state.attributes.get("target_temp_step"))
            if step > 0:
                value = round(value / step) * step
        except (TypeError, ValueError):
            pass
        return value

    async def _async_set_offset(self, target: float, *, force: bool = False) -> None:
        """Write the leaving-water offset and remember successful writes."""
        if not self.enabled and not force:
            return

        entity_id = self._cfg(CONF_HEATING_OFFSET_ENTITY)
        state = self.hass.states.get(entity_id) if entity_id else None
        if state is None:
            _LOGGER.warning("Heizungs-Offset-Entität ist nicht verfügbar: %s", entity_id)
            return

        target = self._round_to_entity_step(state, target)
        current = self._climate_target()
        if current is not None and abs(current - target) < 0.5:
            return

        try:
            await self.hass.services.async_call(
                "climate",
                "set_temperature",
                {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: target},
                blocking=True,
            )
            self.last_write = dt_util.now()
            self.last_offset_written = target
            await self._async_save_runtime()
            _LOGGER.info("Setze Heizungs-Offset %s auf %.1f", entity_id, target)
        except HomeAssistantError as err:
            _LOGGER.warning("Heizungs-Offset konnte nicht gesetzt werden: %s", err)

    async def _async_set_dhw_target(self, target: float, *, force: bool = False) -> None:
        """Write DHW target without changing operation mode; remember writes."""
        if not self.enabled and not force:
            return

        entity_id = self._cfg(CONF_DHW_ENTITY)
        state = self.hass.states.get(entity_id) if entity_id else None
        if state is None:
            _LOGGER.warning("Warmwasser-Entität ist nicht verfügbar: %s", entity_id)
            return

        target = self._round_to_entity_step(state, target)
        _current_temp, current_target, _mode = self._dhw_values()
        if current_target is not None and abs(current_target - target) < 0.5:
            return

        try:
            await self.hass.services.async_call(
                "water_heater",
                "set_temperature",
                {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: target},
                blocking=True,
            )
            self.last_write = dt_util.now()
            self.last_dhw_written = target
            await self._async_save_runtime()
            _LOGGER.info("Setze Warmwasser-Sollwert %s auf %.1f °C", entity_id, target)
        except HomeAssistantError as err:
            _LOGGER.warning("Warmwasser-Sollwert konnte nicht gesetzt werden: %s", err)

    async def async_set_enabled(self, enabled: bool) -> None:
        """Enable/disable active control and persist state."""
        if self.enabled == enabled:
            return

        if not enabled and bool(self._cfg(CONF_RESTORE_ON_DISABLE)):
            await self._async_set_offset(float(self._cfg(CONF_BASE_OFFSET)), force=True)

            _current_temp, current_target, operation_mode = self._dhw_values()
            hygiene_threshold = float(self._cfg(CONF_DHW_HYGIENE_GUARD))
            hygiene_active = (
                operation_mode == "performance"
                or (current_target is not None and current_target >= hygiene_threshold)
            )
            if not hygiene_active:
                await self._async_set_dhw_target(
                    float(self._cfg(CONF_DHW_NORMAL_TARGET)), force=True
                )

        self.enabled = enabled
        await self._async_save_runtime()
        await self.async_request_refresh()

    def _fallback_data(self, status: str) -> OptimizerData:
        """Return useful local data when the forecast is unavailable."""
        dhw_current, dhw_target, _operation_mode = self._dhw_values()
        return OptimizerData(
            status=status,
            forecast_temperature=None,
            forecast_min_temperature=None,
            forecast_max_temperature=None,
            warm_window_start=None,
            warm_window_end=None,
            warm_window_temperature=None,
            next_night_minimum=None,
            temperature_advantage=None,
            boost_active=False,
            warm_window_active=False,
            ramp_active=False,
            room_temperature=self._room_temperature(),
            planned_offset=float(self._cfg(CONF_BASE_OFFSET)),
            dhw_current_temperature=dhw_current,
            dhw_planned_target=dhw_target,
            dhw_comfort_fallback=False,
            dhw_hygiene_guard_active=False,
            plan_generated_at=dt_util.now(),
            last_write=self.last_write,
            last_offset_written=self.last_offset_written,
            last_dhw_written=self.last_dhw_written,
        )

    async def _async_update_data(self) -> OptimizerData:
        """Update forecast, calculate plans/targets and optionally write them."""
        try:
            points = await self._get_hourly_forecast()
        except (HomeAssistantError, ValueError, TypeError) as err:
            _LOGGER.warning("Forecast konnte nicht geladen werden: %s", err)

            if self.enabled:
                await self._async_set_offset(float(self._cfg(CONF_BASE_OFFSET)), force=True)
                _dhw_current, current_target, operation_mode = self._dhw_values()
                hygiene_threshold = float(self._cfg(CONF_DHW_HYGIENE_GUARD))
                hygiene_active = (
                    operation_mode == "performance"
                    or (current_target is not None and current_target >= hygiene_threshold)
                )
                if not hygiene_active:
                    await self._async_set_dhw_target(
                        float(self._cfg(CONF_DHW_NORMAL_TARGET)), force=True
                    )

            return self._fallback_data(
                "forecast_nicht_verfuegbar" if self.enabled else "deaktiviert"
            )

        now = dt_util.now()
        horizon_points = points[:24] if len(points) > 24 else points
        temperatures = [point.temperature for point in horizon_points]
        forecast_temperature = self._closest_temperature(points, now)
        forecast_min = min(temperatures) if temperatures else None
        forecast_max = max(temperatures) if temperatures else None

        windows = self._find_warm_windows(points, now)
        summary_window = next((window for window in windows if window.end > now), None)
        warm_start = summary_window.start if summary_window else None
        warm_end = summary_window.end if summary_window else None
        warm_mean = summary_window.mean_temperature if summary_window else None
        night_min = summary_window.night_minimum if summary_window else None
        advantage = summary_window.advantage if summary_window else None

        room_temperature = self._room_temperature()
        nominal_offset_now, _phase, _steps, _window = self._nominal_offset_at(now, windows)
        planned_offset, boost_active, ramp_active, nominal_steps_now = self._calculate_offset(
            now=now,
            windows=windows,
            room_temperature=room_temperature,
        )
        warm_window_active = self._window_active(now, windows)

        dhw_current, dhw_current_target, operation_mode = self._dhw_values()
        normal_dhw = float(self._cfg(CONF_DHW_NORMAL_TARGET))
        reduced_dhw = float(self._cfg(CONF_DHW_REDUCED_TARGET))
        comfort_min = float(self._cfg(CONF_DHW_COMFORT_MIN))
        hygiene_threshold = float(self._cfg(CONF_DHW_HYGIENE_GUARD))

        dhw_comfort_fallback = bool(dhw_current is not None and dhw_current < comfort_min)
        dhw_hygiene_guard_active = bool(
            operation_mode == "performance"
            or (dhw_current_target is not None and dhw_current_target >= hygiene_threshold)
        )
        nominal_dhw_now = normal_dhw if warm_window_active else reduced_dhw

        if dhw_hygiene_guard_active:
            dhw_planned_target = dhw_current_target
        elif dhw_comfort_fallback:
            dhw_planned_target = normal_dhw
        elif warm_window_active:
            # DHW timing is independent of the room-temperature heating guard.
            dhw_planned_target = normal_dhw
        else:
            dhw_planned_target = reduced_dhw

        heating_plan, dhw_plan = self._build_plans(
            points,
            now=now,
            windows=windows,
        )
        next_change, next_summary, next_offset, next_dhw = self._next_plan_change(
            now=now,
            heating_plan=heating_plan,
            dhw_plan=dhw_plan,
            current_nominal_offset=nominal_offset_now,
            current_nominal_dhw=nominal_dhw_now,
        )

        if not self.enabled:
            status = "deaktiviert"
        elif dhw_hygiene_guard_active:
            status = "hygiene_oder_manueller_boost"
        elif dhw_comfort_fallback:
            status = "warmwasser_komfort"
        elif warm_window_active and boost_active:
            status = "optimales_zeitfenster"
        elif warm_window_active and nominal_steps_now > 0:
            status = "optimales_zeitfenster_raum_guard"
        elif warm_window_active:
            status = "optimales_zeitfenster_ohne_heizboost"
        elif ramp_active:
            status = "temperatur_rampe"
        elif warm_start is not None and now < warm_start:
            status = "wartet_auf_zeitfenster"
        else:
            status = "basisbetrieb"

        if self.enabled:
            await self._async_set_offset(planned_offset)
            if not dhw_hygiene_guard_active and dhw_planned_target is not None:
                await self._async_set_dhw_target(dhw_planned_target)

        return OptimizerData(
            status=status,
            forecast_temperature=forecast_temperature,
            forecast_min_temperature=forecast_min,
            forecast_max_temperature=forecast_max,
            warm_window_start=warm_start,
            warm_window_end=warm_end,
            warm_window_temperature=warm_mean,
            next_night_minimum=night_min,
            temperature_advantage=advantage,
            boost_active=boost_active,
            warm_window_active=warm_window_active,
            ramp_active=ramp_active,
            room_temperature=room_temperature,
            planned_offset=planned_offset,
            dhw_current_temperature=dhw_current,
            dhw_planned_target=dhw_planned_target,
            dhw_comfort_fallback=dhw_comfort_fallback,
            dhw_hygiene_guard_active=dhw_hygiene_guard_active,
            plan_generated_at=now,
            heating_plan=heating_plan,
            dhw_plan=dhw_plan,
            next_change=next_change,
            next_change_summary=next_summary,
            next_offset=next_offset,
            next_dhw_target=next_dhw,
            last_write=self.last_write,
            last_offset_written=self.last_offset_written,
            last_dhw_written=self.last_dhw_written,
        )
