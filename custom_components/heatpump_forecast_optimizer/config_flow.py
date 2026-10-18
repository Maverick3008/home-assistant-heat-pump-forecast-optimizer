"""Config flow for Heat Pump Forecast Optimizer."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import selector

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
    CONF_NAME,
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
)


def _number(minimum: float, maximum: float, step: float = 1.0):
    """Create a number selector."""
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=minimum,
            max=maximum,
            step=step,
            mode=selector.NumberSelectorMode.BOX,
        )
    )


def _optional_entity_schema(
    schema: dict[Any, Any],
    key: str,
    current: dict[str, Any],
    domain: str,
) -> None:
    """Add an optional entity selector, preserving its current default."""
    entity_selector = selector.EntitySelector(
        selector.EntitySelectorConfig(domain=domain)
    )
    if current.get(key):
        schema[vol.Optional(key, default=current[key])] = entity_selector
    else:
        schema[vol.Optional(key)] = entity_selector


def _build_schema(current: dict[str, Any]) -> vol.Schema:
    """Build the setup/options form schema."""
    def value(key: str):
        return current.get(key, DEFAULTS.get(key))

    schema: dict[Any, Any] = {
        vol.Required(CONF_NAME, default=value(CONF_NAME)): selector.TextSelector(),
        (
            vol.Required(
                CONF_WEATHER_ENTITY,
                default=current[CONF_WEATHER_ENTITY],
            )
            if current.get(CONF_WEATHER_ENTITY)
            else vol.Required(CONF_WEATHER_ENTITY)
        ): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="weather")
        ),
        vol.Required(
            CONF_HEATING_OFFSET_ENTITY,
            default=value(CONF_HEATING_OFFSET_ENTITY),
        ): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="climate")
        ),
        vol.Required(
            CONF_DHW_ENTITY,
            default=value(CONF_DHW_ENTITY),
        ): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="water_heater")
        ),
        vol.Required(CONF_DAY_START, default=value(CONF_DAY_START)): selector.TimeSelector(),
        vol.Required(CONF_DAY_END, default=value(CONF_DAY_END)): selector.TimeSelector(),
        vol.Required(
            CONF_WARM_WINDOW_HOURS,
            default=value(CONF_WARM_WINDOW_HOURS),
        ): _number(1, 8, 1),
        vol.Required(
            CONF_FORECAST_HOURS,
            default=value(CONF_FORECAST_HOURS),
        ): _number(24, 72, 1),
        vol.Required(
            CONF_BASE_OFFSET,
            default=value(CONF_BASE_OFFSET),
        ): _number(-10, 10, 1),
        vol.Required(
            CONF_MAX_BOOST_STEPS,
            default=value(CONF_MAX_BOOST_STEPS),
        ): _number(0, 8, 1),
        vol.Required(
            CONF_ADVANTAGE_MEDIUM,
            default=value(CONF_ADVANTAGE_MEDIUM),
        ): _number(0, 20, 0.5),
        vol.Required(
            CONF_ADVANTAGE_STRONG,
            default=value(CONF_ADVANTAGE_STRONG),
        ): _number(0, 20, 0.5),
        vol.Required(
            CONF_ADVANTAGE_MAX,
            default=value(CONF_ADVANTAGE_MAX),
        ): _number(0, 25, 0.5),
        vol.Required(
            CONF_RAMP_HOURS,
            default=value(CONF_RAMP_HOURS),
        ): _number(0, 4, 1),
        vol.Required(
            CONF_DHW_NORMAL_TARGET,
            default=value(CONF_DHW_NORMAL_TARGET),
        ): _number(30, 60, 1),
        vol.Required(
            CONF_DHW_REDUCED_TARGET,
            default=value(CONF_DHW_REDUCED_TARGET),
        ): _number(30, 60, 1),
        vol.Required(
            CONF_DHW_COMFORT_MIN,
            default=value(CONF_DHW_COMFORT_MIN),
        ): _number(30, 60, 1),
        vol.Required(
            CONF_DHW_HYGIENE_GUARD,
            default=value(CONF_DHW_HYGIENE_GUARD),
        ): _number(45, 65, 1),
        vol.Required(
            CONF_ROOM_TARGET,
            default=value(CONF_ROOM_TARGET),
        ): _number(15, 28, 0.1),
        vol.Required(
            CONF_ROOM_UPPER_MARGIN,
            default=value(CONF_ROOM_UPPER_MARGIN),
        ): _number(0, 5, 0.1),
        vol.Required(
            CONF_ROOM_LOWER_MARGIN,
            default=value(CONF_ROOM_LOWER_MARGIN),
        ): _number(0, 5, 0.1),
        vol.Required(
            CONF_RESTORE_ON_DISABLE,
            default=value(CONF_RESTORE_ON_DISABLE),
        ): selector.BooleanSelector(),
    }

    _optional_entity_schema(
        schema,
        CONF_ROOM_TEMP_ENTITY,
        current,
        "sensor",
    )
    return vol.Schema(schema)


class HeatPumpForecastOptimizerConfigFlow(
    config_entries.ConfigFlow,
    domain=DOMAIN,
):
    """Handle setup."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Handle initial setup."""
        if user_input is not None:
            return self.async_create_entry(
                title=user_input.get(CONF_NAME, DEFAULTS[CONF_NAME]),
                data=user_input,
            )

        initial = dict(DEFAULTS)
        initial.update(
            {
                CONF_HEATING_OFFSET_ENTITY: "climate.altherma_leaving_water_offset",
                CONF_DHW_ENTITY: "water_heater.altherma",
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=_build_schema(initial),
        )

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        """Return the options flow."""
        return HeatPumpForecastOptionsFlow(config_entry)


class HeatPumpForecastOptionsFlow(config_entries.OptionsFlow):
    """Handle options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Edit all optimizer settings."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = {**self._config_entry.data, **self._config_entry.options}
        return self.async_show_form(
            step_id="init",
            data_schema=_build_schema(current),
        )
