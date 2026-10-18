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
STORAGE_VERSION = 1


@dataclass(slots=True)
class ForecastPoint:
    """Normalized hourly forecast point."""

    dt: datetime
    temperature: float


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
        self._store: Store[dict[str, bool]] = Store(
            hass,
            STORAGE_VERSION,
            f"{DOMAIN}.{entry.entry_id}",
        )

    async def _async_setup(self) -> None:
        """Restore persistent runtime state."""
        stored = await self._store.async_load()
        if isinstance(stored, dict):
            self.enabled = bool(stored.get("enabled", False))

    def _cfg(self, key: str) -> Any:
        """Read merged config/options with a default fallback."""
        return self.config.get(key, DEFAULTS.get(key))

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
        try:
            return float(state.attributes.get("temperature"))
        except (TypeError, ValueError):
            return None

    def _dhw_values(self) -> tuple[float | None, float | None, str | None]:
        """Return current DHW temperature, target and operation mode."""
        entity_id = self._cfg(CONF_DHW_ENTITY)
        state = self.hass.states.get(entity_id) if entity_id else None
        if state is None:
            return None, None, None

        def as_float(value: Any) -> float | None:
            try:
                return float(value)
            except (TypeError, ValueError):
                return None

        return (
            as_float(state.attributes.get("current_temperature")),
            as_float(state.attributes.get("temperature")),
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
            {
                ATTR_ENTITY_ID: weather_entity,
                "type": "hourly",
            },
            blocking=True,
            return_response=True,
        )

        if not isinstance(response, dict):
            raise HomeAssistantError("Wetterdienst lieferte keine Antwort")

        raw = response.get(weather_entity, {})
        forecasts = raw.get("forecast", []) if isinstance(raw, dict) else []

        now = dt_util.now()
        horizon = now + timedelta(hours=int(self._cfg(CONF_FORECAST_HOURS)))
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

            try:
                temperature = float(raw_temp)
            except (TypeError, ValueError):
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

    def _find_warmest_window(
        self,
        points: list[ForecastPoint],
        now: datetime,
    ) -> tuple[datetime | None, datetime | None, float | None]:
        """Find the warmest contiguous block in the configured daytime window."""
        day_start = self._parse_time(self._cfg(CONF_DAY_START))
        day_end = self._parse_time(self._cfg(CONF_DAY_END))
        hours = max(1, int(self._cfg(CONF_WARM_WINDOW_HOURS)))

        best: tuple[datetime, datetime, float] | None = None

        for index in range(0, len(points) - hours + 1):
            chunk = points[index : index + hours]

            # The window may already have begun, but should not be fully in the past.
            window_end = chunk[-1].dt + timedelta(hours=1)
            if window_end <= now:
                continue

            if len({point.dt.date() for point in chunk}) != 1:
                continue

            if not all(
                self._time_in_window(point.dt.time(), day_start, day_end)
                for point in chunk
            ):
                continue

            contiguous = all(
                timedelta(minutes=45)
                <= chunk[pos + 1].dt - chunk[pos].dt
                <= timedelta(minutes=75)
                for pos in range(len(chunk) - 1)
            )
            if not contiguous:
                continue

            average = mean(point.temperature for point in chunk)
            candidate = (chunk[0].dt, window_end, average)
            if best is None or average > best[2]:
                best = candidate

        return best if best is not None else (None, None, None)

    def _find_night_minimum(
        self,
        points: list[ForecastPoint],
        warm_end: datetime | None,
    ) -> float | None:
        """Find the minimum forecast temperature after the warm block overnight."""
        if warm_end is None:
            return None

        day_start = self._parse_time(self._cfg(CONF_DAY_START))
        day_end = self._parse_time(self._cfg(CONF_DAY_END))
        limit = warm_end + timedelta(hours=16)

        candidates = [
            point.temperature
            for point in points
            if warm_end <= point.dt <= limit
            and not self._time_in_window(point.dt.time(), day_start, day_end)
        ]
        return min(candidates) if candidates else None

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
        return self._read_state_number(
            self.hass,
            self._cfg(CONF_ROOM_TEMP_ENTITY),
        )

    def _calculate_offset(
        self,
        *,
        now: datetime,
        warm_start: datetime | None,
        warm_end: datetime | None,
        advantage: float | None,
        room_temperature: float | None,
    ) -> tuple[float, bool, bool]:
        """Calculate the offset including ramping and optional room guard."""
        base = float(self._cfg(CONF_BASE_OFFSET))
        max_steps = max(0, int(self._cfg(CONF_MAX_BOOST_STEPS)))
        steps = min(self._boost_steps(advantage), max_steps)
        ramp_hours = max(0, int(self._cfg(CONF_RAMP_HOURS)))

        boost_active = False
        ramp_active = False
        applied_steps = 0

        if warm_start is not None and warm_end is not None:
            if warm_start <= now < warm_end:
                boost_active = True
                applied_steps = steps
            elif (
                ramp_hours > 0
                and warm_start - timedelta(hours=ramp_hours) <= now < warm_start
            ):
                ramp_active = True
                applied_steps = max(0, steps - 1) if steps > 1 else steps
            elif (
                ramp_hours > 0
                and warm_end <= now < warm_end + timedelta(hours=ramp_hours)
            ):
                ramp_active = True
                applied_steps = max(0, steps - 1)

        if room_temperature is not None:
            target = float(self._cfg(CONF_ROOM_TARGET))
            upper = float(self._cfg(CONF_ROOM_UPPER_MARGIN))
            lower = float(self._cfg(CONF_ROOM_LOWER_MARGIN))

            # Don't pre-heat an already warm house.
            if room_temperature >= target + upper:
                applied_steps = 0
                boost_active = False
                ramp_active = False

            # If the room is already a little too cold, allow at least one
            # step during the favorable window even with a small advantage.
            elif (
                room_temperature <= target - lower
                and (boost_active or ramp_active)
                and max_steps > 0
            ):
                applied_steps = max(1, applied_steps)

        return base + applied_steps, boost_active, ramp_active

    @staticmethod
    def _round_to_entity_step(
        state: Any,
        value: float,
    ) -> float:
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

    async def _async_set_offset(
        self,
        target: float,
        *,
        force: bool = False,
    ) -> None:
        """Write the Daikin leaving-water offset."""
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
                {
                    ATTR_ENTITY_ID: entity_id,
                    ATTR_TEMPERATURE: target,
                },
                blocking=True,
            )
            _LOGGER.info("Setze Heizungs-Offset %s auf %.1f", entity_id, target)
        except HomeAssistantError as err:
            _LOGGER.warning("Heizungs-Offset konnte nicht gesetzt werden: %s", err)

    async def _async_set_dhw_target(
        self,
        target: float,
        *,
        force: bool = False,
    ) -> None:
        """Write the DHW target without changing the operation mode."""
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
                {
                    ATTR_ENTITY_ID: entity_id,
                    ATTR_TEMPERATURE: target,
                },
                blocking=True,
            )
            _LOGGER.info("Setze Warmwasser-Sollwert %s auf %.1f °C", entity_id, target)
        except HomeAssistantError as err:
            _LOGGER.warning("Warmwasser-Sollwert konnte nicht gesetzt werden: %s", err)

    async def async_set_enabled(self, enabled: bool) -> None:
        """Enable/disable active control and persist state."""
        if self.enabled == enabled:
            return

        if not enabled and bool(self._cfg(CONF_RESTORE_ON_DISABLE)):
            # Restore user-configured baselines. Respect an active high-temperature
            # hygiene/manual cycle instead of lowering it.
            await self._async_set_offset(
                float(self._cfg(CONF_BASE_OFFSET)),
                force=True,
            )

            _current_temp, current_target, operation_mode = self._dhw_values()
            hygiene_threshold = float(self._cfg(CONF_DHW_HYGIENE_GUARD))
            hygiene_active = (
                operation_mode == "performance"
                or (
                    current_target is not None
                    and current_target >= hygiene_threshold
                )
            )
            if not hygiene_active:
                await self._async_set_dhw_target(
                    float(self._cfg(CONF_DHW_NORMAL_TARGET)),
                    force=True,
                )

        self.enabled = enabled
        await self._store.async_save({"enabled": enabled})
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
            ramp_active=False,
            room_temperature=self._room_temperature(),
            planned_offset=float(self._cfg(CONF_BASE_OFFSET)),
            dhw_current_temperature=dhw_current,
            dhw_planned_target=dhw_target,
            dhw_comfort_fallback=False,
            dhw_hygiene_guard_active=False,
        )

    async def _async_update_data(self) -> OptimizerData:
        """Update forecast, calculate targets and optionally write them."""
        try:
            points = await self._get_hourly_forecast()
        except (HomeAssistantError, ValueError, TypeError) as err:
            _LOGGER.warning("Forecast konnte nicht geladen werden: %s", err)

            if self.enabled:
                await self._async_set_offset(
                    float(self._cfg(CONF_BASE_OFFSET)),
                    force=True,
                )

                _dhw_current, current_target, operation_mode = self._dhw_values()
                hygiene_threshold = float(self._cfg(CONF_DHW_HYGIENE_GUARD))
                hygiene_active = (
                    operation_mode == "performance"
                    or (
                        current_target is not None
                        and current_target >= hygiene_threshold
                    )
                )
                if not hygiene_active:
                    await self._async_set_dhw_target(
                        float(self._cfg(CONF_DHW_NORMAL_TARGET)),
                        force=True,
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

        warm_start, warm_end, warm_mean = self._find_warmest_window(points, now)
        night_min = self._find_night_minimum(points, warm_end)
        advantage = (
            warm_mean - night_min
            if warm_mean is not None and night_min is not None
            else None
        )

        room_temperature = self._room_temperature()
        planned_offset, boost_active, ramp_active = self._calculate_offset(
            now=now,
            warm_start=warm_start,
            warm_end=warm_end,
            advantage=advantage,
            room_temperature=room_temperature,
        )

        dhw_current, dhw_current_target, operation_mode = self._dhw_values()
        normal_dhw = float(self._cfg(CONF_DHW_NORMAL_TARGET))
        reduced_dhw = float(self._cfg(CONF_DHW_REDUCED_TARGET))
        comfort_min = float(self._cfg(CONF_DHW_COMFORT_MIN))
        hygiene_threshold = float(self._cfg(CONF_DHW_HYGIENE_GUARD))

        dhw_comfort_fallback = bool(
            dhw_current is not None and dhw_current < comfort_min
        )
        dhw_hygiene_guard_active = bool(
            operation_mode == "performance"
            or (
                dhw_current_target is not None
                and dhw_current_target >= hygiene_threshold
            )
        )

        if dhw_hygiene_guard_active:
            dhw_planned_target = dhw_current_target
        elif dhw_comfort_fallback:
            dhw_planned_target = normal_dhw
        elif boost_active:
            dhw_planned_target = normal_dhw
        else:
            # Lowering the target does not cool the tank. It delays re-heating
            # until the favorable warm forecast window.
            dhw_planned_target = reduced_dhw

        if not self.enabled:
            status = "deaktiviert"
        elif dhw_hygiene_guard_active:
            status = "hygiene_oder_manueller_boost"
        elif dhw_comfort_fallback:
            status = "warmwasser_komfort"
        elif boost_active:
            status = "optimales_zeitfenster"
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
            ramp_active=ramp_active,
            room_temperature=room_temperature,
            planned_offset=planned_offset,
            dhw_current_temperature=dhw_current,
            dhw_planned_target=dhw_planned_target,
            dhw_comfort_fallback=dhw_comfort_fallback,
            dhw_hygiene_guard_active=dhw_hygiene_guard_active,
        )
