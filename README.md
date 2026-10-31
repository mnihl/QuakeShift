# QuakeShift

QuakeShift detects earthquakes in live data from open European seismometer stations using pretrained AI models. It is **carbon-aware**: when the electricity grid is dirty it switches to cheaper models and fewer stations, and when the grid is clean again it re-checks the cheap periods with the big model to find small earthquakes it missed.

Project for *AI Architecture & Cloud Computing*. Everything runs in Docker on a local Kubernetes cluster, on CPUs only, without training any models.

## Documentation

- [Architecture](ARCHITECTURE.md): specification, use cases, components, UML diagrams
- [Architecture decisions (ADRs)](ARCHITECTURE.md#4-architecture-decisions)
- [Local vs server deployment](DEPLOYMENT_COMPARISON.md)
- [Project checklist](CHECKLIST.md)

## Team members

- Cristian Vortolomei (cristianvortolomei)
- Morgan Nihlmar (mnihl)
