# Changelog

All notable changes to this project are documented here.

## [0.2.1] - 2026-10-19

### Added
- 24-36 hour nominal heating-offset plan exposed as `Heizplan` sensor attributes.
- Daily warm-window planning so a warmer tomorrow no longer causes today's useful window to be skipped.
- At least 48 h of internal forecast context for reliable following-night comparison while keeping the visible plan horizon configurable.
- Conservative fallback when a forecast does not extend far enough into the following night.
- Dedicated `Optimales Zeitfenster aktiv` binary sensor.
- 24-36 hour DHW target plan exposed as `Warmwasserplan` sensor attributes.
- Outdoor forecast temperature included in both plans for chart overlays.
- `Nächste geplante Änderung` timestamp with target details.
- Persistent diagnostics for last successful write, last offset and last DHW target.
- Ready-to-copy ApexCharts dashboard examples in `dashboard/`.

### Changed
- Removed the misleading `integration_type: helper` manifest classification. This remains a normal UI-configured custom integration.
- Future heating plan is shown as a nominal forecast curve; the room-temperature guard is evaluated live at execution time.
- DHW plan explicitly documents that comfort/hygiene protection can override the nominal curve live.
- DHW warm-window charging is now independent of the room-temperature heating guard.

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
