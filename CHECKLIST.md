# QuakeShift — Project Checklist

**Presentation deadline:** `05.12.2026`  
**Shared contracts:** [CONTRACTS.md](CONTRACTS.md)

---

## 1. Team Decisions & Kickoff (Do First, Together)

- [ ] **Decide execution mode:** parallel tracks (recommended) vs. sequential staged work.
- [ ] **Assign tracks:** decide who owns **Track A** and who owns **Track B** (target ~50/50 workload and commits).
- [ ] **Fix Git & PR workflow:**
  - [ ] Verify both team members' Git commit emails are linked to their GitHub accounts.
  - [ ] Switch to feature branches + pull requests only (no direct pushes to `main`), with cross-reviews on every PR.
- [ ] **Review and sign off on [CONTRACTS.md](CONTRACTS.md)** (Kafka schemas, Postgres DDL, HTTP endpoints, env vars, metric names).
- [ ] **Dataset & model sanity check (half-day):**
  - [ ] Select **5–10 densely spaced regional European stations** and **1–2 real past earthquakes (M ≥ 3)** from GEOFON + EMSC reference catalogue so the 3-station association rule triggers reliably.
  - [ ] Pin the replay dataset (or download script) and EMSC reference file in the repo.
  - [ ] Benchmark SeisBench **PhaseNet** and **EQTransformer** on a laptop CPU (required window lengths, inference time, RAM) and update window size in [CONTRACTS.md](CONTRACTS.md) if needed.

---

## 2. Track A — Seismic Pipeline, API, Evaluation & Core UML *(Unassigned)*

*Can be developed and tested locally with Docker Compose (Kafka + Postgres) without waiting for Kubernetes.*

### Documentation & UML fixes
- [ ] Fix [use-cases.puml](docs/architecture/use-cases.puml): remove `<<include>>` from UC3→UC1, make Grid Carbon Source an external actor, add Operator actor, render monochrome, re-export SVG.
- [ ] Fix [components.puml](docs/architecture/components.puml): strict UML component notation (provided/required interfaces, `<<use>>` dependencies, no actors/queues/databases/data-flow labels, monochrome), re-export SVG.
- [ ] Fix [class.puml](docs/architecture/class.puml): add types/visibility, remove runtime `CarbonController ..> Picker` link, rename `Event.origin_time` → `first_pick_time`, add missing domain classes, monochrome, re-export SVG.
- [ ] Create **Crash & Deduplication sequence diagram** (replaces dropped UC1 linear diagram) showing Kafka polling, picker pod crash mid-window, redelivery, and deduplicated upsert.
- [ ] Write **ADR-010: Latency definition, delivery guarantees & 3-level deduplication** and update [ADR-002](docs/adr/002-postgresql-results-store.md).

### Implementation & tests
- [ ] Local `docker-compose.yml` (single-broker KRaft Kafka + PostgreSQL) for fast local development.
- [ ] `ingestor`: replays recorded GEOFON waveforms with overlapping windows, idempotent Kafka producer, latency header timestamps, `/health`, `/ready`, `/metrics`.
- [ ] `pickers` + `backfill-job`: single configurable Python package supporting `eco` (STA/LTA + PhaseNet on core stations), `balanced` (PhaseNet), `performance` (EQTransformer), and `backfill` batch seek mode; `/health`, `/ready`, `/metrics`.
- [ ] `associator`: regional association rule, pick-level (±0.5 s) and event-level (PostgreSQL GiST exclusion upsert) deduplication, manual Kafka offset commit after DB write, `/health`, `/ready`, `/metrics`.
- [ ] `results-api` + minimal HTML/JS operator page: `GET /events`, `GET /history/profiles`, `GET /report/carbon` (counterfactual vs. always-performance / always-eco), and UI controls calling `carbon-controller` override/threshold endpoints.
- [ ] `evaluator`: compares detected events against EMSC (recall, precision, detection delay, eco vs. back-fill recovery) and exports Prometheus metrics.
- [ ] Dockerfiles + unit tests (`pytest`) for deduplication, association, pickers, and API.

---

## 3. Track B — Kubernetes, Carbon Control, Energy, CI/CD & Ops UML *(Unassigned)*

*Can be developed and tested on `kind` using a lightweight mock picker container until Track A's real image is ready.*

### Documentation & UML fixes
- [ ] Create new **UML Deployment Diagram** (`deployment.puml` / `.svg`, monochrome): host → `kind` cluster → `quakeshift` namespace, `picker-eco/balanced/performance` Deployments, Kafka & Postgres StatefulSets, Back-fill Job, container artifacts.
- [ ] Fix [seq-mode-switch.puml](docs/architecture/seq-mode-switch.puml): monochrome, cover **low, medium, and high** carbon bands in an `alt` fragment, include lag read, cooldown/hysteresis, readiness wait, and failure/rollback branch.
- [ ] Fix [seq-backfill.puml](docs/architecture/seq-backfill.puml): monochrome, include forecast-based scheduling, Kafka consumer polling (not push), and updating `backfill_periods` in PostgreSQL.
- [ ] Update [ADR-004](docs/adr/004-profile-switch-by-scaling.md), [ADR-005](docs/adr/005-carbon-controller.md) (fix SLO guard direction + replica scaling + aftershock boost), [ADR-006](docs/adr/006-green-backfill.md) (forecast & deadline tracking), [ADR-008](docs/adr/008-measurement-and-monitoring.md) (host CodeCarbon + per-pod CPU attribution + accounting boundary), and [ADR-009](docs/adr/009-ci-cd.md) (chaos pod-kill test).

### Implementation & ops
- [ ] `kind` cluster config + Kubernetes manifests (`k8s/`): Kafka (KRaft) & Postgres StatefulSets, 3 picker Deployments with readiness probes, Back-fill Job template, RBAC for `carbon-controller`, Prometheus & Grafana.
- [ ] 20-line mock picker container for independent Track B testing before integration.
- [ ] `carbon-signal`: pluggable source supporting deterministic scenario JSON **and** real free European grid feed (e.g., SMARD / Energy-Charts) with `GET /intensity` and `GET /forecast`.
- [ ] `carbon-controller`:
  - [ ] Intensity-band profile switching with cooldown, hysteresis, readiness check before scale-down, and rollback on failure.
  - [ ] **Lag-driven replica scaling** (`1..N` within active profile) + corrected **SLO guard** (step *down* to a lighter model only if scaling replicas is not enough).
  - [ ] **Aftershock boost:** temporary 10-minute `performance` override after a detected live earthquake.
  - [ ] **Forecast & deadline-aware back-fill scheduling:** schedule back-fill Job into cleanest forecast window before Kafka retention expires.
  - [ ] Operator REST endpoints: `GET /status`, `POST /override`, `DELETE /override`, `PUT /thresholds`.
- [ ] **Host energy accounting & dashboards:** host-side CodeCarbon Prometheus exporter + per-pod energy attribution via cAdvisor CPU seconds; Grafana dashboards (cluster vs. picker energy, latency SLO, Kafka lag, profile switches, recall/precision).
- [ ] **CI/CD (GitHub Actions):** lint + unit tests, `kind` replay test with **mid-replay picker pod-kill chaos test** (assert zero lost/duplicate events), and GHCR container builds on `main`.

---

## 4. Integration, Experiments & Presentation (Both)

- [ ] Integrate Track A's real Docker images into Track B's `kind` manifests and remove the mock picker.
- [ ] Update [ARCHITECTURE.md](ARCHITECTURE.md) and `overview.svg` (with explicit color legend) to match the final implemented system.
- [ ] Run controlled replay experiments comparing **always-performance**, **always-eco**, and **carbon-aware + back-fill** (measure recall, pipeline latency p95, full-cluster vs. picker-only kWh and gCO₂e).
- [ ] Write the final report (architecture, ADRs, UML, sustainability trade-offs, energy accounting boundary, experiment results).
- [ ] Rehearse the 15-minute presentation and Q&A across **both** tracks so either teammate can explain any component or code block.
