# QuakeShift

QuakeShift is a **carbon-aware earthquake detection project** for *AI Architecture & Cloud Computing*. The planned system uses pretrained models on open European seismometer data, adjusts processing to the electricity grid's carbon intensity, and re-checks recordings from eco periods when cleaner electricity is available.

**Current status:** architecture documents, diagrams, nine architecture decision records (ADRs) and the repository/team PDF are prepared. The architecture review identified open issues tracked in the [checklist](CHECKLIST.md#before-implementation). Application services, tests, deployment manifests and CI/CD are not implemented yet.

The documented baseline is **CPU-only Docker containers on local Kubernetes**, with no model training. The planned pipeline is:

`GEOFON / replay → ingestor → Kafka → picker → Kafka → associator → PostgreSQL → results API`

Pickers mark P- and S-wave arrival times at each station; the associator combines picks across stations into earthquake candidates. See the [architecture](ARCHITECTURE.md) for the processing profiles and quality targets, which still need validation.

## Documentation

- [Project checklist](CHECKLIST.md): completed work, open review items and implementation milestones
- [Architecture](ARCHITECTURE.md): specification, use cases, components and rendered UML diagrams
- [Architecture decisions (ADRs)](ARCHITECTURE.md#4-architecture-decisions): current choices, alternatives and trade-offs; these replace the earlier comparison table
- [Diagram sources and editing guide](docs/architecture/README.md): PlantUML sources, SVG previews and export instructions
- [Local vs server deployment](DEPLOYMENT_COMPARISON.md): deployment trade-offs and the local-first recommendation
- [Original project intent (PDF)](QuakeShift-intent-final.pdf): the initial proposal; use the architecture and ADRs for the current design
- [Repository and team (PDF)](output/pdf/QuakeShift-repository-and-team.pdf): clickable repository URL and team names, prepared for the first checkpoint

## Team members

- Cristian Vortolomei (cristianvortolomei)
- Morgan Nihlmar (mnihl)
