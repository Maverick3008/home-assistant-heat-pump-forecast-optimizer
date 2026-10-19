"""Binary sensors for Heat Pump Forecast Optimizer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)

from . import HeatPumpForecastConfigEntry
from .entity import HeatPumpForecastEntity
from .models import OptimizerData


@dataclass(frozen=True, kw_only=True)
class OptimizerBinarySensorDescription(BinarySensorEntityDescription):
    """Describe an optimizer binary sensor."""

    value_fn: Callable[[OptimizerData], bool]


BINARY_SENSORS: tuple[OptimizerBinarySensorDescription, ...] = (
    OptimizerBinarySensorDescription(
        key="boost_active",
        name="Forecast Boost aktiv",
        icon="mdi:weather-sunny-alert",
        value_fn=lambda data: data.boost_active,
    ),
    OptimizerBinarySensorDescription(
        key="warm_window_active",
        name="Optimales Zeitfenster aktiv",
        icon="mdi:clock-check-outline",
        value_fn=lambda data: data.warm_window_active,
    ),
    OptimizerBinarySensorDescription(
        key="ramp_active",
        name="Temperatur Rampe aktiv",
        icon="mdi:stairs-up",
        value_fn=lambda data: data.ramp_active,
    ),
    OptimizerBinarySensorDescription(
        key="dhw_comfort_fallback",
        name="Warmwasser Komfortanforderung",
        icon="mdi:water-alert",
        value_fn=lambda data: data.dhw_comfort_fallback,
    ),
    OptimizerBinarySensorDescription(
        key="dhw_hygiene_guard_active",
        name="Warmwasser Hygiene Schutz",
        icon="mdi:shield-check",
        value_fn=lambda data: data.dhw_hygiene_guard_active,
    ),
)


class HeatPumpForecastBinarySensor(HeatPumpForecastEntity, BinarySensorEntity):
    """Optimizer binary sensor."""

    entity_description: OptimizerBinarySensorDescription

    def __init__(self, coordinator, entry, description) -> None:
        super().__init__(coordinator, entry)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

    @property
    def is_on(self) -> bool:
        """Return current boolean value."""
        return self.entity_description.value_fn(self.coordinator.data)


async def async_setup_entry(
    hass,
    entry: HeatPumpForecastConfigEntry,
    async_add_entities,
) -> None:
    """Set up binary sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        HeatPumpForecastBinarySensor(coordinator, entry, description)
        for description in BINARY_SENSORS
    )
