"""Heat Pump Forecast Optimizer integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import PLATFORMS
from .coordinator import HeatPumpForecastCoordinator

type HeatPumpForecastConfigEntry = ConfigEntry[HeatPumpForecastCoordinator]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HeatPumpForecastConfigEntry,
) -> bool:
    """Set up Heat Pump Forecast Optimizer."""
    config = {**entry.data, **entry.options}
    coordinator = HeatPumpForecastCoordinator(hass, entry, config)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: HeatPumpForecastConfigEntry,
) -> bool:
    """Unload the integration."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload_entry(
    hass: HomeAssistant,
    entry: HeatPumpForecastConfigEntry,
) -> None:
    """Reload when options change."""
    await hass.config_entries.async_reload(entry.entry_id)
