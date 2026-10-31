# QuakeShift project checklist

Updated: 31 October 2026. Completed items below concern architecture documentation. Application code, deployment, CI/CD and monitoring remain proposed work.

## Accomplished

- [x] Read the project intent and identify features, quality targets and architecturally significant use cases.
- [x] Write a standalone, concise [architecture overview](ARCHITECTURE.md), including definitions of the data sources, protocols and detection methods.
- [x] Describe processing modes, deferred reprocessing, recovery and resource-aware redeployment.
- [x] Create PlantUML [component](docs/architecture/components.puml), [sequence](docs/architecture/sequence.puml) and [use-case](docs/architecture/use-cases.puml) diagrams.
- [x] Validate PlantUML syntax, render SVG versions and visually inspect the diagrams.
- [x] Embed expandable diagrams and document [VS Code viewing/editing instructions](docs/architecture/README.md).
- [x] Describe the proposed GitHub Actions workflow, Prometheus/Grafana monitoring and carbon metrics.
- [x] Document [architecture choices, alternatives and trade-offs](ARCHITECTURE_COMPARISON.md).

## Next: Cristian reviews with an agent

- [ ] **Cristian + an agent:** review [ARCHITECTURE.md](ARCHITECTURE.md) for clarity, completeness and feasibility within the two-person project scope.
- [ ] **Cristian + an agent:** pay particular attention to the diagrams: check UML meaning, software component boundaries, interface labels, message directions and agreement with the written architecture.
- [ ] **Cristian + an agent:** review the [architecture comparison table](ARCHITECTURE_COMPARISON.md); challenge the rationale and identify where a simpler alternative would be sufficient.
- [ ] Check the live/background workflow, duplicate handling and recovery; confirm that eco-period recordings remain available for reprocessing.
- [ ] Check controller responsibilities, deployment permissions, rollout/rollback behavior and ownership of scaling settings.
- [ ] Record accepted decisions, proposed changes and unresolved questions; update both documents and regenerate affected SVGs after review.

## After review

- [ ] Discuss local versus server deployment, including the actual available hardware, access, cost and energy-measurement limitations.
- [ ] After that discussion, create the deployment pros/cons document and record the team's decision. No deployment decision is final yet.
- [ ] Agree the initial region, stations, replay dataset and evaluation criteria; benchmark model latency, resource needs and energy on candidate hardware.
- [ ] Implement the first end-to-end replay path: ingestion -> picker -> association -> persisted results/API.
- [ ] Add durable job recovery, processing modes and deferred reprocessing.
- [ ] Implement and test resource/carbon control and redeployment.
- [ ] Implement GitHub Actions, deployment checks, monitoring dashboards and carbon metrics.
- [ ] Validate detection quality, the 60-second target, stable live queues and total energy/carbon cost including catch-up work.
