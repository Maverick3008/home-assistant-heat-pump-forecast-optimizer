"""Master switch for Heat Pump Forecast Optimizer."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity

from . import HeatPumpForecastConfigEntry
from .entity import HeatPumpForecastEntity


class ForecastOptimizationSwitch(HeatPumpForecastEntity, SwitchEntity):
    """Enable or disable active forecast control."""

    _attr_name = "Automatische Regelung"
    _attr_icon = "mdi:heat-pump-outline"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_automatic_control"

    @property
    def is_on(self) -> bool:
        """Return whether automatic writes are enabled."""
        return self.coordinator.enabled

    @property
    def available(self) -> bool:
        """Keep the master switch usable even if the forecast fails."""
        return True

    async def async_turn_on(self, **kwargs) -> None:
        """Enable automatic control."""
        await self.coordinator.async_set_enabled(True)

    async def async_turn_off(self, **kwargs) -> None:
        """Disable automatic control."""
        await self.coordinator.async_set_enabled(False)


async def async_setup_entry(
    hass,
    entry: HeatPumpForecastConfigEntry,
    async_add_entities,
) -> None:
    """Set up the master switch."""
    async_add_entities(
        [ForecastOptimizationSwitch(entry.runtime_data, entry)]
    )
