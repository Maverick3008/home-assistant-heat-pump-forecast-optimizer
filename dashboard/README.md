# Dashboard examples

v0.2.1 exposes future targets in two sensor attributes:

- **Heizplan** → attribute `plan`
- **Warmwasserplan** → attribute `plan`

Each list item includes an ISO timestamp, the planned target and the forecast
outdoor temperature. This allows future values to be graphed without creating
Home Assistant helper entities.

## Files

- `apexcharts-card.yaml` – complete vertical-stack example with diagnostics,
  heating plan and DHW plan.
- `heating-plan-apexcharts.yaml` – heating chart only.
- `dhw-plan-apexcharts.yaml` – DHW chart only.

The examples use the popular HACS custom card **ApexCharts Card**. If Home
Assistant generated different entity IDs, replace the example entity IDs with
the actual IDs from **Developer tools → States**.

## Important

The heating curve is the **nominal forecast plan**. A configured room-temperature
guard is evaluated live when each target is due because future room temperature
is not known. Therefore a visible future boost can be suppressed at execution
time if the house is already warm enough.

The DHW curve is also nominal. Comfort fallback and a detected hygiene/manual
high-temperature cycle can override it live.

The large plan attributes are explicitly excluded from Recorder history by the
integration. They remain available live for dashboards without filling the
Home Assistant database with a new 36-hour plan every refresh.
