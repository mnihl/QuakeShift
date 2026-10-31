# QuakeShift project checklist

## Assignment 1 — architecture (31.10)

- [x] Project specification: features and non-functional requirements ([ARCHITECTURE.md §1](ARCHITECTURE.md#1-project-specification))
- [x] Architecturally significant use cases ([§2](ARCHITECTURE.md#2-architecturally-significant-use-cases))
- [x] UML in PlantUML: use-case, component, sequence (3) and class diagrams ([§3](ARCHITECTURE.md#3-architecture))
- [x] Architecture decisions: ADR-001 to ADR-009 ([§4](ARCHITECTURE.md#4-architecture-decisions))
- [ ] Both team members have read the docs and can explain every decision

## Assignment 2 — implementation (21.11): at least 50 %, deployed to Kubernetes

- [ ] Choose 5–10 stations and one past earthquake for replay; download the data
- [ ] Measure PhaseNet and EQTransformer speed on our laptops
- [ ] Ingestor (replay first) → Kafka → live picker → associator → PostgreSQL
- [ ] Results API
- [ ] Run everything on kind with Kubernetes manifests

## Final submission

- [ ] Carbon signal service and carbon controller (profile switch)
- [ ] Back-fill job
- [ ] Live GEOFON ingestion
- [ ] CodeCarbon, Prometheus and Grafana dashboards
- [ ] GitHub Actions: tests, replay test, image build, deploy
- [ ] Evaluator vs EMSC; check the targets N1–N8
- [ ] Presentation and written report
