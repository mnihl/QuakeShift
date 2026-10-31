# QuakeShift project checklist

Documentation is prepared and has been reviewed with an agent. Open design issues remain; implementation has not started in this repository.

## Assignment 1 — architecture (31.10)

- [x] Document requirements, use cases and [architecture](ARCHITECTURE.md), with validated UML diagrams.
- [x] Record [nine ADRs](ARCHITECTURE.md#4-architecture-decisions) and [deployment trade-offs](DEPLOYMENT_COMPARISON.md).
- [x] Review the updated documents with an agent and identify follow-up work below.
- [x] Prepare the [repository and team PDF](output/pdf/QuakeShift-repository-and-team.pdf).
- [x] Both team members have read the docs and can explain every decision

## Before implementation

- [ ] Agree the latency definition and evaluation targets; confirm local hardware and deployment scope.
- [ ] Correct the backlog response and define safe Kafka handover, retries and back-fill progress tracking.
- [ ] Define model windowing, earthquake association and duplicate-safe event matching.
- [ ] Agree energy-accounting boundaries; update affected ADRs and diagrams, including missing interfaces and readiness checks.

## Assignment 2 — implementation (21.11): at least 50 %, deployed to Kubernetes

- [ ] Choose 5–10 stations and one past earthquake for replay; download the data
- [ ] Benchmark PhaseNet and EQTransformer latency, memory and energy on our laptops
- [ ] Build the replay pipeline: ingestor → Kafka → picker → associator → PostgreSQL, plus the results API
- [ ] Deploy on kind and verify the pipeline with replay and restart tests

## Final submission

- [ ] Carbon signal, controller, profile switching and back-fill
- [ ] Live GEOFON ingestion
- [ ] CodeCarbon, Prometheus and Grafana dashboards
- [ ] GitHub Actions: tests, replay test, image build, deploy
- [ ] Evaluator vs EMSC; check the targets N1–N8
- [ ] Presentation and written report
