"""Sensors for Heat Pump Forecast Optimizer."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import EntityCategory, MATCH_ALL, UnitOfTemperature

from . import HeatPumpForecastConfigEntry
from .entity import HeatPumpForecastEntity
from .models import OptimizerData


@dataclass(frozen=True, kw_only=True)
class OptimizerSensorDescription(SensorEntityDescription):
    """Describe an optimizer sensor."""

    value_fn: Callable[[OptimizerData], Any]


SENSORS: tuple[OptimizerSensorDescription, ...] = (
    OptimizerSensorDescription(
        key="status", name="Status", icon="mdi:heat-pump", value_fn=lambda data: data.status
    ),
    OptimizerSensorDescription(
        key="forecast_temperature",
        name="Außentemperatur Prognose",
        icon="mdi:thermometer",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda data: data.forecast_temperature,
    ),
    OptimizerSensorDescription(
        key="forecast_min_temperature",
        name="Prognose Minimum 24 h",
        icon="mdi:thermometer-chevron-down",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda data: data.forecast_min_temperature,
    ),
    OptimizerSensorDescription(
        key="forecast_max_temperature",
        name="Prognose Maximum 24 h",
        icon="mdi:thermometer-chevron-up",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda data: data.forecast_max_temperature,
    ),
    OptimizerSensorDescription(
        key="warm_window_start",
        name="Optimales Zeitfenster Start",
        icon="mdi:clock-start",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data.warm_window_start,
    ),
    OptimizerSensorDescription(
        key="warm_window_end",
        name="Optimales Zeitfenster Ende",
        icon="mdi:clock-end",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data.warm_window_end,
    ),
    OptimizerSensorDescription(
        key="warm_window_temperature",
        name="Optimales Zeitfenster Mitteltemperatur",
        icon="mdi:weather-sunny",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda data: data.warm_window_temperature,
    ),
    OptimizerSensorDescription(
        key="next_night_minimum",
        name="Nächstes Nachtminimum",
        icon="mdi:weather-night",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda data: data.next_night_minimum,
    ),
    OptimizerSensorDescription(
        key="temperature_advantage",
        name="Temperaturvorteil",
        icon="mdi:delta",
        native_unit_of_measurement="K",
        value_fn=lambda data: data.temperature_advantage,
    ),
    OptimizerSensorDescription(
        key="room_temperature",
        name="Raumtemperatur",
        icon="mdi:home-thermometer",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda data: data.room_temperature,
    ),
    OptimizerSensorDescription(
        key="planned_offset",
        name="Geplanter Heizungs-Offset",
        icon="mdi:tune-vertical",
        native_unit_of_measurement="K",
        value_fn=lambda data: data.planned_offset,
    ),
    OptimizerSensorDescription(
        key="dhw_current_temperature",
        name="Warmwasser Isttemperatur",
        icon="mdi:water-thermometer",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda data: data.dhw_current_temperature,
    ),
    OptimizerSensorDescription(
        key="dhw_planned_target",
        name="Geplante Warmwasser Solltemperatur",
        icon="mdi:water-boiler",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda data: data.dhw_planned_target,
    ),
    OptimizerSensorDescription(
        key="last_write",
        name="Letzter Schreibvorgang",
        icon="mdi:database-clock",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.last_write,
    ),
    OptimizerSensorDescription(
        key="last_offset_written",
        name="Zuletzt gesetzter Heizungs-Offset",
        icon="mdi:tune-vertical-variant",
        native_unit_of_measurement="K",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.last_offset_written,
    ),
    OptimizerSensorDescription(
        key="last_dhw_written",
        name="Zuletzt gesetzte Warmwasser Solltemperatur",
        icon="mdi:water-check",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.last_dhw_written,
    ),
)


class HeatPumpForecastSensor(HeatPumpForecastEntity, SensorEntity):
    """Calculated optimizer sensor."""

    entity_description: OptimizerSensorDescription

    def __init__(self, coordinator, entry, description: OptimizerSensorDescription) -> None:
        super().__init__(coordinator, entry)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator.data)


class HeatPumpForecastPlanSensor(HeatPumpForecastEntity, SensorEntity):
    """Expose future plan points as attributes for chart cards."""

    # Future plan arrays are useful for the live dashboard but would create a
    # large Recorder history entry every forecast refresh. Keep the live
    # attributes while explicitly excluding them from Recorder history.
    _unrecorded_attributes = frozenset({MATCH_ALL})

    def __init__(self, coordinator, entry, kind: str) -> None:
        super().__init__(coordinator, entry)
        self._kind = kind
        self._attr_unique_id = f"{entry.entry_id}_{kind}_plan"
        if kind == "heating":
            self._attr_name = "Heizplan"
            self._attr_icon = "mdi:chart-timeline-variant"
        else:
            self._attr_name = "Warmwasserplan"
            self._attr_icon = "mdi:chart-line"

    @property
    def native_value(self) -> int:
        plan = self._plan
        return len(plan)

    @property
    def _plan(self) -> list[dict[str, Any]]:
        if self._kind == "heating":
            return self.coordinator.data.heating_plan
        return self.coordinator.data.dhw_plan

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        plan = self._plan
        value_key = "offset" if self._kind == "heating" else "temperature"
        changes: list[dict[str, Any]] = []
        previous: float | None = None
        for item in plan:
            current = item.get(value_key)
            if current is None:
                continue
            current = float(current)
            if previous is None or abs(current - previous) >= 0.5:
                change = {
                    "datetime": item.get("datetime"),
                    value_key: current,
                    "phase": item.get("phase"),
                }
                if item.get("conditional_room_guard"):
                    change["conditional_room_guard"] = True
                changes.append(change)
                previous = current

        data = self.coordinator.data
        return {
            "plan": plan,
            "changes": changes,
            "generated_at": data.plan_generated_at.isoformat()
            if data.plan_generated_at
            else None,
            "points": len(plan),
            "horizon_hours": (
                round(
                    (
                        datetime.fromisoformat(plan[-1]["datetime"])
                        - datetime.fromisoformat(plan[0]["datetime"])
                    ).total_seconds()
                    / 3600,
                    1,
                )
                if len(plan) >= 2
                else 0
            ),
            "note": (
                "Der Heizplan ist die nominale Forecast-Kurve. Ein konfigurierter "
                "Raumtemperatur-Schutz wird zum Ausführungszeitpunkt live geprüft."
                if self._kind == "heating"
                else "Komfort- und Hygiene-Schutz können den Warmwasserplan live überschreiben."
            ),
        }


class HeatPumpForecastNextChangeSensor(HeatPumpForecastEntity, SensorEntity):
    """Expose the next nominal schedule change."""

    _attr_name = "Nächste geplante Änderung"
    _attr_icon = "mdi:calendar-clock"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_next_planned_change"

    @property
    def native_value(self):
        return self.coordinator.data.next_change

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data
        return {
            "summary": data.next_change_summary,
            "next_offset": data.next_offset,
            "next_dhw_target": data.next_dhw_target,
        }


async def async_setup_entry(hass, entry: HeatPumpForecastConfigEntry, async_add_entities) -> None:
    """Set up optimizer sensors."""
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = [
        HeatPumpForecastSensor(coordinator, entry, description)
        for description in SENSORS
    ]
    entities.extend(
        [
            HeatPumpForecastPlanSensor(coordinator, entry, "heating"),
            HeatPumpForecastPlanSensor(coordinator, entry, "dhw"),
            HeatPumpForecastNextChangeSensor(coordinator, entry),
        ]
    )
    async_add_entities(entities)
