# Heat Pump Forecast Optimizer 0.2.1

This release makes the optimizer transparent before it changes the heat pump and improves multi-day scheduling.

## New plan curves

Two new sensors expose the complete future schedule in their `plan` attribute:

- `Heizplan`: timestamp, nominal offset, outdoor temperature, phase and boost steps.
- `Warmwasserplan`: timestamp, DHW target, outdoor temperature and phase.

The configured forecast horizon determines the length (36 hours by default).

## Next change

`Nächste geplante Änderung` shows when the nominal schedule changes next and
contains the upcoming offset / DHW target in its attributes.

## Write diagnostics

New diagnostic entities show:

- last successful write time;
- last heating offset written;
- last DHW target written.

These values survive a Home Assistant restart.

## Dashboard

`dashboard/apexcharts-card.yaml` contains ready-to-copy examples for a future
heating-offset curve and a future DHW curve, both overlaid with forecast outdoor
temperature.

## Important planning behavior

The heating chart is a **nominal forecast plan**. Future room temperature cannot
be known, so the configured room-temperature guard is evaluated live at the
moment a target would be applied. Likewise, DHW comfort/hygiene protection can
override the nominal DHW curve.

## Metadata fix

The misleading `integration_type: helper` entry has been removed from the
manifest. The project remains a normal Home Assistant custom integration with
its own config flow, coordinator, entities and device.

## Daily planning fix

v0.2.0 selected one globally warmest window from the forecast horizon. That could
make the optimizer wait for a warmer tomorrow and skip a still-useful period
today. v0.2.1 selects the best remaining window **per forecast day**.

DHW scheduling is also independent of the room-temperature heating guard: an
already-warm room can suppress floor-heating preheat without preventing DHW from
using the favorable outdoor-temperature window.
