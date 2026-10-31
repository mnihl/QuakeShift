# QuakeShift project checklist

Documentation is drafted; implementation and deployment are still pending.

## Done

- [x] Draft the [architecture](ARCHITECTURE.md), covering requirements, use cases, CI/CD, monitoring and carbon-aware operation.
- [x] Create and validate UML diagrams, with rendered previews and [viewing instructions](docs/architecture/README.md).
- [x] Document [architecture alternatives](ARCHITECTURE_COMPARISON.md) and [deployment options](DEPLOYMENT_COMPARISON.md).

## Review — Cristian with an agent

- [ ] Review [ARCHITECTURE.md](ARCHITECTURE.md), especially the diagrams, interfaces and feasibility for two people.
- [ ] Review [architecture choices and alternatives](ARCHITECTURE_COMPARISON.md); identify useful simplifications.
- [ ] Review [local versus server deployment](DEPLOYMENT_COMPARISON.md), including the local-first recommendation and available hardware.
- [ ] Agree decisions and update the documents and diagrams.

## Build and validate

- [ ] Choose test data, hardware and evaluation criteria; build the first end-to-end replay pipeline.
- [ ] Add recovery, carbon-aware modes, reprocessing and resource-aware redeployment.
- [ ] Set up GitHub Actions, deployment and monitoring, including carbon metrics.
- [ ] Evaluate detection quality, latency, reliability and total energy/carbon cost.
