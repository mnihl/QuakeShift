# ADR-008: CodeCarbon with Prometheus and Grafana

**Status:** Accepted · **Use cases:** UC2, UC4, UC5

## Context

We must report carbon metrics and show dashboards for system health and model behaviour. The carbon controller also needs live numbers (Kafka lag) to decide.

## Decision

- **CodeCarbon** runs inside every picker and the back-fill job and estimates energy (kWh). Emissions = energy × carbon intensity of the scenario (gCO₂/kWh).
- Every service exposes **`/metrics`**: latency, Kafka lag, active profile, CPU, memory, energy, emissions, and the evaluator's recall and precision.
- **Prometheus** collects the metrics; **Grafana** shows dashboards and alerts (lag keeps growing, a station stops sending, a switch fails).
- We report energy and gCO₂e **per station-hour** and **per detected earthquake**.

## Alternatives

| Option | Why not |
| --- | --- |
| Kepler (Kubernetes energy exporter) | Needs hardware counters that are often missing inside VMs and kind; more setup. Possible later. |
| External power meter | Most accurate, but we do not have one. |
| Cloud Carbon Footprint | Built for cloud bills; we run locally. |
| ELK stack | Focused on logs; our main data are numbers over time. |

## Consequences

- ✅ Standard tools that are well documented and easy to demo.
- ✅ The same metrics serve the dashboards, the alerts and the controller.
- ❌ CodeCarbon only **estimates** energy inside containers, so we compare profiles with each other and do not claim exact values.
- ❌ Prometheus and Grafana use some CPU and memory themselves.

## Sustainability

Measuring is what lets us prove that eco saves energy (N4). We keep scrape intervals moderate (for example 15 s) so monitoring does not become a noticeable load itself.
