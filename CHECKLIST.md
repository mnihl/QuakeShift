# QuakeShift project checklist

**Presentation deadline · 5 December 2026**

**Shared reference · [Interface contracts](CONTRACTS.md)**

Use this as one shared list. Either teammate can pick up any unchecked item. Discuss shared decisions together and review each other's pull requests.

## 1. Agree on the basics

- [x] Verify that GitHub links the published commits to the expected accounts. Use feature branches and pull requests, with a teammate review before merging to `main`.
- [x] Choose 5–10 nearby European stations and 1–2 recorded earthquakes of magnitude 3 or higher. Commit the GEOFON replay download script and the matching EMSC reference CSV. Check that the three-station rule can trigger on the chosen data.
  - **Replay 1 · Umbertide.** Run `python scripts/download_replay.py` for the magnitude 4.6 event on 9 March 2023. The three-minute clip has three channels at 100 Hz from six INGV stations. Reviewed P arrivals for the eco stations `IV.ATVO`, `IV.ATMI`, and `IV.ATFO` span 1.16 seconds (INGV event `34297011`).
  - **Replay 2 · Tyrol.** Run `python scripts/download_replay.py tyrol` for the magnitude 3.6 event near Gschnitz on 31 October 2024. The three-minute clip has three channels at 100 Hz from nine Austrian stations. EMSC P arrivals for the eco stations `OE.SQTA`, `OE.MOTA`, `OE.WATA`, and `OE.FETA` span 4.99 seconds.
  - Use the EMSC row whose origin time falls inside the clip being evaluated. [Download script](scripts/download_replay.py) · [EMSC reference CSV](data/replay/emsc_reference.csv)
- [x] Benchmark PhaseNet and EQTransformer on the laptop CPU. Use 60-second windows published every 10 seconds.
  - Both models found enough matching P waves in each replay. PhaseNet took 0.12–0.15 s per three-minute clip and peaked at 421 MiB of RAM. EQTransformer took 0.30–0.42 s and peaked at 431 MiB. [Benchmark details](docs/adr/003-three-processing-profiles.md#cpu-benchmark)
- [x] Review the [interface contracts](CONTRACTS.md) with the confirmed window size.
  - [x] **Latency.** Use first P arrival to first live database commit. Record the 60-second target and how to report timing.
  - [x] **Duplicate messages and events.** Merge overlapping event ranges within one regional replay. Record how to handle repeated windows, picks, and back-fill updates.

## 2. Get one earthquake through the system

### Set up the shared cluster

- [x] Add the local [kind config](kind-config.yaml) and the [quakeshift namespace](k8s/base/namespace.yaml).
- [x] Set up Kafka under `k8s/kafka/` with a single-broker KRaft StatefulSet, a topic-init Job, and a lag exporter for Prometheus. Use six partitions for `waveforms`, three for `picks`, and seven days of retention for both.
- [ ] Set up PostgreSQL under `k8s/postgres/` with a StatefulSet, persistent volume claim, Service, and initial SQL for `events`, `profile_changes`, and `backfill_periods`.

### Connect replay, detection, and results

- [ ] Build the `ingestor`. Replay overlapping GEOFON windows, send them to `waveforms` with an idempotent Kafka producer, and include the `t_ingested` timing header. Add `/health`, `/ready`, and `/metrics`.
  - [x] Read the recordings and build 60-second windows every 10 seconds. Verified 78 windows for Umbertide and 117 for Tyrol. [Replay reader](ingestor/replay.py)
  - [x] Send the windows to Kafka at the original speed. A consumer received all 78 Umbertide windows with their waveform samples and timing headers intact. [Replay sender](ingestor/send.py)
- [ ] Build one Python package for the pickers and the backfill job. Support `eco` (STA/LTA and PhaseNet on core stations), `balanced` (PhaseNet), and `performance` (EQTransformer), using the `live-pickers` consumer group. Backfill uses its own group, seeks to the recorded time, writes to `picks`, and commits offsets after a successful write. Add `/health`, `/ready`, and `/metrics`.
- [ ] Add `k8s/pickers/` manifests for the ingestor, `picker-eco`, `picker-balanced`, `picker-performance`, and the backfill Job template. Include readiness probes, CPU and memory limits, and the `CORE_STATIONS` ConfigMap.
- [ ] Build and deploy the `associator`. Read `picks` with the `associator` group, merge repeated picks within ±0.5 seconds, and apply the three-station rule. Use the agreed PostgreSQL rule to insert or update an event and only commit the Kafka offset after the database write. Add `/health`, `/ready`, and `/metrics`.
- [ ] Add a small synthetic `picks` producer so the associator can be tested before the real picker is ready.
- [ ] Build and deploy `results-api` with `GET /events` and `GET /history/profiles`. Use a seeded PostgreSQL database to test it independently.
- [ ] Run one known earthquake through the real pipeline on `kind`. Check that the expected event appears in `GET /events`.

## 3. Show the carbon-aware behavior

### Switch modes and run backfill

- [ ] Build and deploy `carbon-signal`. Support a repeatable JSON scenario and a free European grid feed such as SMARD or Energy-Charts. Serve `GET /intensity`, `GET /forecast`, and `/metrics`.
- [ ] Build and deploy `carbon-controller` with Kubernetes permissions for scaling `picker-*` Deployments and managing `backfill-*` Jobs. Use a small mock picker Deployment to test the controller before the real images are ready.
  - [ ] Switch modes for all three grid levels. Add cooldown and hysteresis, wait for the new picker to be ready before stopping the old one, and roll back if the switch fails.
  - [ ] Use Kafka lag from Prometheus to scale the active mode from 1 to N replicas. Step down to a lighter mode only if scaling is insufficient, and update the older controller decision to match.
  - [ ] Boost to `performance` for 10 minutes after a live event is recorded in PostgreSQL.
  - [ ] Schedule `backfill-<id>` Jobs in the cleanest forecast window before Kafka's seven-day retention expires. Track progress in `backfill_periods`.
  - [ ] Add `GET /status`, `POST /override`, `DELETE /override`, and `PUT /thresholds`.
- [ ] Add the minimal HTML/JS operator page. Connect the mode and threshold controls to the controller and test them against a stub controller URL. Add `GET /report/carbon` to compare emissions, recall, and estimated cloud compute cost with always-performance and always-eco.

### Measure and display results

- [ ] Set up Prometheus under `k8s/monitoring/prometheus/` with a Deployment, Service, and RBAC. Configure pod discovery using `prometheus.io/scrape: "true"` annotations, cAdvisor metrics, and a host CodeCarbon scrape target.
- [ ] Set up Grafana under `k8s/monitoring/grafana/` with a Deployment, Service, provisioned Prometheus datasource, and ConfigMap loading JSON from `monitoring/grafana/dashboards/`.
- [ ] Run CodeCarbon on the host and export `quakeshift_host_energy_kwh_total` to Prometheus. Use cAdvisor CPU time and PromQL to estimate each pod's share. Document what the host estimate includes and how the picker share is calculated.
- [ ] Build the evaluator as a Kubernetes Job. Compare detections against the EMSC reference CSV for recall, precision, detection delay, and backfill recovery. Export the results to Prometheus.
- [ ] Add `ai-pipeline.json` with pick rate by phase and mode, confidence distribution, inference and stage latency, Kafka throughput and lag, recall and precision, and backfill recovery.
- [ ] Add `system-energy.json` with cluster and picker kWh and gCO₂e, pipeline p95 against the 60-second target, active mode and switches, Kafka lag and replica counts. Add alerts for growing lag, stale stations, and failed switches.

## 4. Test, finish the diagrams, and prepare the presentation

### Tests and integration

- [ ] Add Dockerfiles and `pytest` unit tests for the ingestor, pickers, associator, results API, evaluator, carbon signal, and carbon controller. Expose `/metrics` on the long-running services as defined in the contracts.
- [ ] Send structured JSON logs to stdout. Include `timestamp`, `service`, and `profile`. Keep `window_id` or `event_id` in the seismic and results logs, and `reason` in the associator, carbon signal, and controller logs.
- [ ] Set up GitHub Actions to lint and run `pytest` on pull requests, run a `kind` replay test, and build and publish images to GHCR on `main`. Stop a picker mid-replay and check that no events were lost or duplicated.
- [ ] Run the integrated system on `kind` with the real images. Check full replay, mode switches, backfill, and both dashboards. Keep the synthetic producer and mock picker for isolated tests.

### Assignment 1 feedback and architecture

- [ ] Fix [use-cases.puml](docs/architecture/use-cases.puml). Remove `<<include>>` from UC3 to UC1, show the Grid Carbon Source outside the system, and add an Operator actor. Keep UC1 at overview level.
- [ ] Fix [components.puml](docs/architecture/components.puml). Use UML provided and required interfaces and `<<use>>` dependencies. Keep actors, queues, database icons, and runtime data-flow arrows in the overview or sequence diagrams as appropriate.
- [ ] Fix [class.puml](docs/architecture/class.puml). Add types, visibility, and missing domain classes. Remove the runtime `CarbonController ..> Picker` link and rename `origin_time` to `first_pick_time`.
- [ ] Create `deployment.puml` and its SVG. Show the host, `kind` cluster, `quakeshift` namespace, Deployments, StatefulSets, backfill Job, and container artifacts.
- [ ] Fix [seq-mode-switch.puml](docs/architecture/seq-mode-switch.puml). Show low (performance), medium (balanced), and high (eco) in an `alt` block, with lag checks, cooldown, hysteresis, readiness, and rollback.
- [ ] Fix [seq-backfill.puml](docs/architecture/seq-backfill.puml). Show forecast scheduling, Kafka polling, and updates to `backfill_periods`.
- [ ] Draw the crash and deduplication sequence. Show Kafka polling, a picker crashing mid-window, redelivery, and a database update that avoids creating a duplicate.
- [ ] Render the UML diagrams in monochrome and re-export the SVGs.
- [x] Record the timing and duplicate rules in [ADR-010](docs/adr/010-latency-and-deduplication.md). Align [ADR-002](docs/adr/002-postgresql-results-store.md) with the agreed database schema and event matching rule.
- [ ] Update [ADR-004](docs/adr/004-profile-switch-by-scaling.md) through [ADR-009](docs/adr/009-ci-cd.md) for mode switching and scaling, the aftershock boost, forecast and retention deadlines, containers versus serverless and region versus grid intensity, host energy accounting, and the picker crash test.
- [ ] Update [ARCHITECTURE.md](ARCHITECTURE.md) and the [overview diagram](docs/architecture/overview.svg) to match the system that runs. Give the overview a clear color key.

### Experiments and presentation

- [ ] Compare always-performance, always-eco, and carbon-aware with backfill on the same recordings. Record recall, p95 pipeline latency, cluster and picker kWh separately, gCO₂e, and estimated cloud compute cost.
- [ ] Write the final report covering the architecture, decisions, UML, trade-offs, energy accounting boundary, and experiment results.
- [ ] Rehearse the 15-minute presentation and Q&A together so either teammate can explain the system and its results.
