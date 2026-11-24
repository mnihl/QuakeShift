# QuakeShift — Project Checklist

**Presentation deadline:** `05.12.2026`  
**Shared contracts:** [CONTRACTS.md](CONTRACTS.md)

Both tracks are designed so **each teammate gets hands-on experience with Kubernetes, Kafka, Prometheus, and Grafana** while working mostly asynchronously after a short kickoff.

| Technology | Track A *(Ingestion, Pickers, Results & AI Obs)* | Track B *(Association, Carbon Control, Energy & CI/CD)* |
| --- | --- | --- |
| **Kubernetes** | `kind` config, Kafka StatefulSet, picker/ingestor/API Deployments (probes, limits, ConfigMaps), backfill & evaluator Jobs, Grafana Deployment | Postgres StatefulSet, Prometheus Deployment, associator/signal/controller Deployments + RBAC, K8s API scaling & Job spawning, `kind` pod-kill chaos test |
| **Kafka** | KRaft broker + topics + lag exporter, idempotent producer (`ingestor`), consumer groups `live-pickers` & `backfill` timestamp seek | Consumer group `associator` w/ manual commit after DB write, synthetic `picks` test producer, lag-driven scaling & retention-deadline tracking |
| **Prometheus** | `/metrics` on Track A services, Kafka lag exporter, PromQL for pick rates, stage latencies & evaluation scores | Prometheus setup (pod-annotation discovery + cAdvisor), `/metrics` on Track B services, host CodeCarbon exporter & per-pod CPU energy PromQL |
| **Grafana** | Grafana deployment + datasource/dashboard provisioning; **AI & Seismic Pipeline** dashboard | **System Health, Carbon & Energy** dashboard + alert rules (growing lag, stale station, switch failure) |

---

## 1. Kickoff & Shared Baseline (Do First, Together)

- [ ] **Assign Track A & Track B** (target ~50/50 commits) and sign off on [CONTRACTS.md](CONTRACTS.md).
- [ ] **Fix Git & PR workflow:** verify GitHub commit emails; enforce feature branches + PRs + cross-reviews (no pushes to `main`).
- [ ] **Pin dataset & EMSC reference:** pick **5–10 regional European stations** and **1–2 real M ≥ 3 earthquakes** from GEOFON + EMSC so the 3-station rule triggers reliably; commit replay download script & EMSC CSV.
- [ ] **Benchmark SeisBench on laptop CPU:** measure PhaseNet & EQTransformer window size, latency, and RAM; update window length in [CONTRACTS.md](CONTRACTS.md) if needed.

> **Async handoff tip:** Merge each track's **Cluster Infra PR** first (Days 1–2). Once Kafka, Postgres, Prometheus, and Grafana are in `k8s/`, both teammates run the identical `kind` stack locally and build all remaining services asynchronously.

---

## 2. Track A — Ingestion, ML Pickers, Results & AI Observability *(Unassigned)*

### Cluster infra & Grafana base *(merge first)*
- [ ] `kind` cluster config (`kind-config.yaml`) + `quakeshift` namespace manifest (`k8s/base/`).
- [ ] **Kafka on K8s (`k8s/kafka/`):** single-broker KRaft StatefulSet, topic-init Job (`waveforms` 6p/7d, `picks` 3p/7d), and Kafka lag exporter exposing consumer-group lag to Prometheus.
- [ ] **Grafana on K8s (`k8s/monitoring/grafana/`):** Deployment + Service with provisioned Prometheus datasource and dashboard-as-code ConfigMap loading `monitoring/grafana/dashboards/*.json`.

### Kafka pipeline, ML pickers & API
- [ ] `ingestor`: GEOFON replay with overlapping windows, idempotent Kafka producer (`waveforms`), latency headers (`t_ingested`), `/health`, `/ready`, `/metrics`.
- [ ] `pickers` + `backfill-job`: single Python package supporting `eco` (STA/LTA + PhaseNet on core stations), `balanced` (PhaseNet), `performance` (EQTransformer), and `backfill` seek mode (`waveforms` → `picks`, manual offset commit); `/health`, `/ready`, `/metrics`.
- [ ] K8s manifests (`k8s/pickers/`): `ingestor` Deployment, `picker-eco` / `picker-balanced` / `picker-performance` Deployments (readiness probes, CPU/RAM limits, `CORE_STATIONS` ConfigMap), and `backfill` Job template.
- [ ] `results-api` + minimal HTML/JS operator UI + K8s Deployment: `GET /events`, `GET /history/profiles`, `GET /report/carbon` (counterfactual emissions, recall & estimated cloud compute cost vs. always-performance / always-eco), plus override/threshold controls calling `carbon-controller` *(test solo with seeded Postgres + stub controller URL)*.
- [ ] `evaluator` + K8s Job: compare detected events against EMSC (recall, precision, detection delay, eco vs. back-fill recovery) and export Prometheus metrics.

### Observability, tests & packaging
- [ ] **Grafana dashboard (`ai-pipeline.json`):** pick rate by phase/profile, confidence distribution, inference & stage latency, Kafka throughput/lag, evaluator recall/precision & back-fill recovery.
- [ ] Structured JSON logs (`timestamp`, `service`, `profile`, `window_id`/`event_id`), Dockerfiles, and `pytest` unit tests for `ingestor`, `pickers`, `results-api`, and `evaluator`.

### Docs, UML & ADRs
- [ ] Fix [use-cases.puml](docs/architecture/use-cases.puml) (drop `<<include>>` UC3→UC1, add Grid Carbon Source & Operator actors, monochrome, re-export SVG).
- [ ] Fix [components.puml](docs/architecture/components.puml) (strict UML interfaces + `<<use>>`, remove actors/queues/DBs/data-flow labels, monochrome, re-export SVG).
- [ ] Fix [class.puml](docs/architecture/class.puml) (types/visibility, drop `CarbonController ..> Picker`, rename `origin_time` → `first_pick_time`, add missing classes, monochrome, re-export SVG).
- [ ] Create **Crash & Deduplication** sequence diagram (Kafka polling, mid-window picker crash, redelivery, deduplicated upsert).
- [ ] Write **ADR-010** (latency definition, at-least-once delivery & 3-level deduplication).

---

## 3. Track B — Association, Carbon Control, Energy & CI/CD *(Unassigned)*

### Cluster infra & Prometheus base *(merge first)*
- [ ] **PostgreSQL on K8s (`k8s/postgres/`):** StatefulSet, PVC, Service, and DDL init (`events`, `profile_changes`, `backfill_periods` from [CONTRACTS.md](CONTRACTS.md)).
- [ ] **Prometheus on K8s (`k8s/monitoring/prometheus/`):** Deployment, Service, and RBAC configured for Kubernetes pod-annotation auto-scraping (`prometheus.io/scrape: "true"`), cAdvisor metrics, and host CodeCarbon scrape target.

### Kafka associator & carbon control
- [ ] `associator` + K8s Deployment: Kafka consumer (`picks`, group `associator`), ±0.5 s pick dedup, 3-station regional rule, PostgreSQL GiST exclusion upsert, **manual offset commit after DB write**; `/health`, `/ready`, `/metrics`.
- [ ] Independent test harnesses: 20-line synthetic `picks` Kafka producer (to test `associator` solo) + 20-line mock picker Deployment (to test `carbon-controller` scaling/Jobs before Track A's images are ready).
- [ ] `carbon-signal` + K8s Deployment: pluggable scenario JSON **and** free European grid feed (e.g., SMARD / Energy-Charts) serving `GET /intensity`, `GET /forecast`, and `/metrics`.
- [ ] `carbon-controller` + K8s Deployment & scoped **RBAC** (`picker-*` Deployments + `backfill-*` Jobs):
  - [ ] Intensity-band profile switching with cooldown, hysteresis, readiness check before scale-down, and rollback on failure.
  - [ ] Lag-driven replica scaling (`1..N` via Prometheus Kafka lag) + corrected **SLO guard** (step *down* to a lighter profile only if scaling replicas is insufficient).
  - [ ] **Aftershock boost:** 10-minute `performance` override triggered by live events in PostgreSQL.
  - [ ] **Forecast & deadline-aware back-fill:** spawn `backfill-<id>` K8s Jobs in the cleanest forecast window before Kafka's 7-day retention expires and track status in `backfill_periods`.
  - [ ] Operator REST API: `GET /status`, `POST /override`, `DELETE /override`, `PUT /thresholds`.

### Energy, observability, tests & CI/CD
- [ ] **Host energy accounting:** host-side CodeCarbon Prometheus exporter (`quakeshift_host_energy_kwh_total`) + cAdvisor per-pod CPU attribution PromQL queries.
- [ ] **Grafana dashboard (`system-energy.json`) & alerts:** cluster vs. picker kWh & gCO₂e, pipeline latency p95 vs. 60 s SLO, active profile & switches, Kafka lag & replicas, plus alerts (growing lag, stale station, failed switch).
- [ ] Structured JSON logs (`timestamp`, `service`, `profile`, `reason`), Dockerfiles, and `pytest` unit tests for `associator`, `carbon-signal`, and `carbon-controller`.
- [ ] **CI/CD (GitHub Actions):** PR lint + `pytest`, `kind` replay with **mid-replay picker pod-kill chaos test** (assert zero lost/duplicate events), and GHCR image builds on `main`.

### Docs, UML & ADRs
- [ ] Create monochrome **UML Deployment Diagram** (`deployment.puml` / `.svg`): host → `kind` → `quakeshift` namespace, Deployments, StatefulSets, Back-fill Job, containers.
- [ ] Fix [seq-mode-switch.puml](docs/architecture/seq-mode-switch.puml) (monochrome, low/medium/high `alt` bands, lag read, cooldown/hysteresis, readiness wait, rollback).
- [ ] Fix [seq-backfill.puml](docs/architecture/seq-backfill.puml) (monochrome, forecast scheduling, Kafka polling, `backfill_periods` update).
- [ ] Update [ADR-002](docs/adr/002-postgresql-results-store.md) (GiST dedup & schema) and [ADR-004](docs/adr/004-profile-switch-by-scaling.md)–[ADR-009](docs/adr/009-ci-cd.md) (SLO guard direction, replica scaling, aftershock boost, forecast/deadline back-fill, containers vs. serverless & region vs. grid intensity, host CodeCarbon + accounting boundary, chaos pod-kill test).

---

## 4. Integration, Experiments & Presentation (Both)

- [ ] Swap Track B's mock picker and synthetic `picks` script for Track A's real images on `kind` and verify full end-to-end replay + back-fill + dashboards.
- [ ] Update [ARCHITECTURE.md](ARCHITECTURE.md) and `overview.svg` (with explicit color legend) to match the implemented system.
- [ ] Run controlled replay experiments comparing **always-performance**, **always-eco**, and **carbon-aware + back-fill** (recall, p95 pipeline latency, full-cluster vs. picker kWh, gCO₂e, estimated cloud compute cost).
- [ ] Write the final report (architecture, ADRs, UML, sustainability trade-offs, energy accounting boundary, experiment results).
- [ ] Rehearse the 15-minute presentation and Q&A across **both** tracks so either teammate can explain any component or code block.
