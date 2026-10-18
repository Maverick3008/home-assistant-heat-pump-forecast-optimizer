"""Sensors for Heat Pump Forecast Optimizer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import UnitOfTemperature

from . import HeatPumpForecastConfigEntry
from .entity import HeatPumpForecastEntity
from .models import OptimizerData


@dataclass(frozen=True, kw_only=True)
class OptimizerSensorDescription(SensorEntityDescription):
    """Describe an optimizer sensor."""

    value_fn: Callable[[OptimizerData], Any]


SENSORS: tuple[OptimizerSensorDescription, ...] = (
    OptimizerSensorDescription(
        key="status",
        name="Status",
        icon="mdi:heat-pump",
        value_fn=lambda data: data.status,
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
)


class HeatPumpForecastSensor(HeatPumpForecastEntity, SensorEntity):
    """Calculated optimizer sensor."""

    entity_description: OptimizerSensorDescription

    def __init__(
        self,
        coordinator,
        entry,
        description: OptimizerSensorDescription,
    ) -> None:
        super().__init__(coordinator, entry)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

    @property
    def native_value(self) -> Any:
        """Return sensor value."""
        return self.entity_description.value_fn(self.coordinator.data)


async def async_setup_entry(
    hass,
    entry: HeatPumpForecastConfigEntry,
    async_add_entities,
) -> None:
    """Set up optimizer sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        HeatPumpForecastSensor(coordinator, entry, description)
        for description in SENSORS
    )
