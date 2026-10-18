"""Base entity for Heat Pump Forecast Optimizer."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import HeatPumpForecastConfigEntry
from .const import CONF_NAME, DOMAIN
from .coordinator import HeatPumpForecastCoordinator


class HeatPumpForecastEntity(CoordinatorEntity[HeatPumpForecastCoordinator]):
    """Base optimizer entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HeatPumpForecastCoordinator,
        entry: HeatPumpForecastConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry

    @property
    def device_info(self) -> DeviceInfo:
        """Return integration device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=self._entry.data.get(CONF_NAME, self._entry.title),
            manufacturer="Home Assistant Custom Integration",
            model="Forecast Heat Pump Optimizer",
        )
