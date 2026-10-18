# Changelog

All notable changes to this project are documented here.

## [0.2.0] - 2026-10-18

### Added
- Forecast-driven heating optimization for weather-compensated heat pumps.
- Direct support for Daikin Altherma-style leaving-water offset entities such as
  `climate.altherma_leaving_water_offset`.
- DHW optimization through `water_heater.*` entities.
- Dynamic boost strength based on the difference between the warmest daytime
  forecast window and the following night minimum.
- Configurable ramping before and after the warm window.
- Optional room-temperature guard to avoid overheating.
- DHW comfort fallback when tank temperature gets too low.
- Hygiene/manual-boost guard which avoids lowering high DHW targets.
- Master switch; automatic control is disabled by default.
- Local Home Assistant brand icons (Home Assistant 2026.3+).
- HACS and hassfest GitHub Actions validation.

## [0.1.0] - 2026-10-18

### Added
- Initial prototype.
