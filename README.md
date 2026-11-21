# QuakeShift

QuakeShift is a **carbon-aware earthquake detection system** for *AI Architecture & Cloud Computing*. It runs pretrained seismic models on open European seismometer data, adapts processing profiles and replica counts to the electricity grid's carbon intensity and latency SLOs, and time-shifts back-fill of eco periods into cleaner grid windows.

**Repository:** <https://github.com/mnihl/QuakeShift>

**Current status:** Architecture baseline, nine ADRs, shared interface contracts ([CONTRACTS.md](CONTRACTS.md)), and the execution checklist ([CHECKLIST.md](CHECKLIST.md)) are in place. Next up: track assignment, UML/ADR updates from Assignment 1 feedback, and parallel implementation of Track A and Track B.

The baseline runs **CPU-only Docker containers on local Kubernetes (`kind`)**, with no model training:

`GEOFON replay → ingestor → Kafka → picker → Kafka → associator → PostgreSQL → results API`

Pickers mark P- and S-wave arrival times per station; the associator combines picks across stations into deduplicated earthquake events. A carbon controller switches picker profiles, scales replicas under lag, boosts sensitivity for aftershocks, and schedules green back-fill Jobs.

## Documentation

- [Project checklist](CHECKLIST.md): team decisions, Track A / Track B deliverables, and presentation milestones
- [Interface contracts](CONTRACTS.md): Kafka topics/schemas, PostgreSQL DDL, HTTP APIs, K8s conventions, and latency/deduplication definitions
- [Architecture](ARCHITECTURE.md): specification, use cases, components, and diagrams *(updates tracked in checklist)*
- [Architecture decisions (ADRs)](ARCHITECTURE.md#4-architecture-decisions): design choices, alternatives, and sustainability trade-offs
- [Diagram editing guide](docs/architecture/README.md): PlantUML sources and SVG export instructions
- [Local vs server deployment](DEPLOYMENT_COMPARISON.md): deployment trade-offs and the local-first rationale

## Team members

- Morgan Nihlmar (`mnihl`)
- Cristian Vortolomei (`cristianvortolomei`)
