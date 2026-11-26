# QuakeShift — Shared Interface Contracts

This document defines the messages, database tables, endpoints, and settings shared by the services in the [project checklist](CHECKLIST.md).

> **Status.** Reviewed for the first local replay. The [project checklist](CHECKLIST.md) tracks the build and tests.

---

## 1. Timing and delivery

### Latency
- **60-second target (N1).** Measure from the first P-wave arrival in the configured station set to the first successful database commit. Apply the target to each M ≥ 3 event in every profile.
- **Replay check.** Run at `1×` and add `replay_offset_s` to the earliest reviewed P arrival. Use that same reference in every profile. Log the time PostgreSQL acknowledges the commit so the replay check can compare the two. Report missed events alongside the timings.
- **Live measurements.** Subtract the earliest P arrival among the event's picks from the commit time. Apply the replay offset to the arrival first. Save the result in `events.pipeline_latency_s` and record it in the live histogram after the first live commit. Leave unavailable timings blank. Back-fill-only events have no live latency.
- **Clock and stage measurements.** Keep the original timestamps in waveform messages and picks. Pass `replay_offset_s` from the waveform payload to the pick headers and use zero for a real-time station feed. Track the third-station-to-save time for debugging. Use `t_ingested` and `t_picked` to help trace buffering, Kafka, inference, association, and database time. Report EMSC origin-to-commit delay separately on the same clock.
- **Reports.** Show individual timings for short replays. Calculate experiment median, p95, and maximum from the saved live samples by profile, with the sample count. Use the histogram for an estimated 10-minute dashboard p95 and show no data when there are no observations.

### Deduplication (3 Levels)
Delivery is **at-least-once** across Kafka; consumers commit offsets **only after** their downstream write succeeds.

| Level | Identity | Mechanism |
| --- | --- | --- |
| **1. Waveform window** | Kafka key `"{network}.{station}"`, payload field `window_id = "{network}.{station}:{window_start_iso}"` | Idempotent Kafka producer (`enable.idempotence=true`). Reprocessing a window on crash or profile switch is expected and safe. |
| **2. Pick** | Same `(station, phase)` with `pick_time` within **±0.5 s** | Associator merges matching picks inside its rolling window and keeps the highest `probability`. Covers redelivery, overlapping windows, and back-fill picks. |
| **3. Event** | Overlapping time ranges (`event_window`) in a single regional run | Merge the picks and stations into the existing event, or insert a new event when there is no match. PostgreSQL's GiST exclusion constraint prevents overlapping rows. |

Use one regional array and one replay run per result set. Start each independent comparison with fresh results. Form the half-open event range `[first_pick_time − 5 s, last_pick_time + 10 s)` using original waveform timestamps. Start with those padding values and test live and back-fill matches during replay. A time-only rule can merge two distinct earthquakes if their padded ranges overlap.

1. In a transaction, look for an overlap using `SELECT ... FOR UPDATE`. Insert if there is no match. Flag matches with multiple saved events for review and leave those rows intact.
2. For one match, merge stations and saved JSONB picks using the level 2 pick rule. Recalculate `station_count`, the first and last pick times, and `event_window`. Keep the original `source`, `detected_by_profile`, `pipeline_latency_s`, and `created_at`. Set `updated_by` and `updated_at` for the latest change.
3. If a concurrent insert causes an exclusion violation, roll back and retry once in a fresh transaction. Acknowledge the Kafka offset after the write commits.

---

## 2. Kafka Contract

- **Broker:** Single-broker Apache Kafka (KRaft mode).
- **Consumer groups:**
  - `live-pickers` — shared by all three live picker Deployments (`picker-eco`, `picker-balanced`, `picker-performance`).
  - `backfill` — used exclusively by Kubernetes back-fill Jobs.
  - `associator` — used by the associator service.

### Topics

| Topic | Key | Partitions | Retention | Producer | Consumers |
| --- | --- | --- | --- | --- | --- |
| `waveforms` | `{network}.{station}` | 6 (≥ max picker replicas) | 7 days (168 h) | `ingestor` | `live-pickers`, `backfill` |
| `picks` | `{network}.{station}` | 3 | 7 days | `live-pickers`, `backfill` | `associator` |

### Message Schemas (JSON, UTF-8)

**`waveforms` message.** Once the buffer fills, publish a trailing 60-second window every 10 seconds. Each channel contains 6,000 samples at 100 Hz, and `window_end` is exclusive. The `t_ingested` Kafka header carries the same UTC timestamp as `ingested_at`. EQTransformer takes the full window, and SeisBench runs PhaseNet on shorter pieces of it. The example shows two sample values per channel. [CPU benchmark](docs/adr/003-three-processing-profiles.md#cpu-benchmark)
```json
{
  "window_id": "GE.APE:2024-05-01T10:00:00Z",
  "station": "GE.APE",
  "sample_rate_hz": 100,
  "window_start": "2024-05-01T10:00:00.000Z",
  "window_end": "2024-05-01T10:01:00.000Z",
  "channels": {
    "Z": [0.001, -0.002],
    "N": [0.0, 0.001],
    "E": [-0.001, 0.0]
  },
  "ingested_at": "2024-05-08T10:01:00.120Z",
  "replay_offset_s": 604800.0
}
```

**`picks` message:**
```json
{
  "pick_id": "GE.APE:P:2024-05-01T10:00:12.340Z:balanced",
  "window_id": "GE.APE:2024-05-01T10:00:00Z",
  "station": "GE.APE",
  "phase": "P",
  "pick_time": "2024-05-01T10:00:12.340Z",
  "probability": 0.91,
  "profile": "balanced",
  "model_version": "phasenet-instance-v2",
  "source": "live",
  "ingested_at": "2024-05-08T10:01:00.120Z",
  "picked_at": "2024-05-08T10:01:01.450Z"
}
```
- `phase`: `"P"` or `"S"`
- `profile`: `"eco"` | `"balanced"` | `"performance"`
- `source`: `"live"` | `"backfill"`
- Use the tested INSTANCE version 2 weights for both pickers. Set `model_version` to `phasenet-instance-v2` or `eqtransformer-instance-v2`.

---

## 3. PostgreSQL Contract

PostgreSQL stores **results and control history only** (never raw waveforms).

```sql
CREATE TABLE IF NOT EXISTS events (
    id                  BIGSERIAL PRIMARY KEY,
    first_pick_time     TIMESTAMPTZ NOT NULL,
    last_pick_time      TIMESTAMPTZ NOT NULL,
    event_window        TSTZRANGE NOT NULL,
    station_count       INTEGER NOT NULL CHECK (station_count >= 3),
    stations            TEXT[] NOT NULL,
    picks               JSONB NOT NULL,
    detected_by_profile TEXT NOT NULL CHECK (detected_by_profile IN ('eco', 'balanced', 'performance')),
    source              TEXT NOT NULL CHECK (source IN ('live', 'backfill')),
    updated_by          TEXT NOT NULL CHECK (updated_by IN ('live', 'backfill')),
    pipeline_latency_s  DOUBLE PRECISION,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    EXCLUDE USING gist (event_window WITH &&)
);

CREATE TABLE IF NOT EXISTS profile_changes (
    id                  BIGSERIAL PRIMARY KEY,
    changed_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    from_profile        TEXT,
    to_profile          TEXT NOT NULL CHECK (to_profile IN ('eco', 'balanced', 'performance')),
    carbon_intensity    DOUBLE PRECISION NOT NULL,
    kafka_lag           BIGINT NOT NULL DEFAULT 0,
    replicas            INTEGER NOT NULL DEFAULT 1,
    reason              TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS backfill_periods (
    id                  BIGSERIAL PRIMARY KEY,
    period_start        TIMESTAMPTZ NOT NULL,
    period_end          TIMESTAMPTZ NOT NULL,
    retention_deadline  TIMESTAMPTZ NOT NULL,
    status              TEXT NOT NULL CHECK (status IN ('pending', 'scheduled', 'running', 'done', 'expired')),
    scheduled_for       TIMESTAMPTZ,
    job_name            TEXT,
    events_added        INTEGER NOT NULL DEFAULT 0,
    events_updated      INTEGER NOT NULL DEFAULT 0,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

- **Aftershock boost.** `carbon-controller` checks for events first detected live using `WHERE created_at >= NOW() - INTERVAL '10 minutes' AND source = 'live'`. This includes live events later updated by back-fill.

---

## 4. HTTP API Contracts

Every long-running HTTP service exposes:
- `GET /health` → `200 {"status": "ok"}` (Kubernetes liveness probe)
- `GET /ready` → `200 {"status": "ready"}` once models / Kafka / DB are initialized, else `503` (Kubernetes readiness probe — required for safe profile switches)
- `GET /metrics` → Prometheus text format

### `carbon-signal` (default port `8001`)
- `GET /intensity`
  ```json
  {
    "timestamp": "2026-11-21T12:00:00Z",
    "intensity_gco2_kwh": 245.0,
    "band": "medium",
    "source": "scenario",
    "zone": "AT"
  }
  ```
- `GET /forecast?hours=24`
  ```json
  {
    "source": "scenario",
    "zone": "AT",
    "points": [
      {"timestamp": "2026-11-21T13:00:00Z", "intensity_gco2_kwh": 190.0}
    ]
  }
  ```

### `carbon-controller` (default port `8002`)
- `GET /status` → current profile, active replicas, override state, aftershock-boost state, latest intensity, current lag, pending back-fill count.
- `POST /override` — body: `{"profile": "performance", "duration_minutes": 30, "reason": "operator test"}`
- `DELETE /override` — clears manual override and returns to carbon-governed mode.
- `PUT /thresholds` — body: `{"low_max_gco2_kwh": 150, "high_min_gco2_kwh": 300, "cooldown_seconds": 180}`

### `results-api` (default port `8000`)
- `GET /` — minimal static HTML/JS operator & results page (shows events, carbon report, current controller status, and calls override/threshold controls).
- `GET /events?since=&until=&profile=&source=` — list detected earthquakes from PostgreSQL. The source filter uses the first detection's `source`.
- `GET /events/{id}` — single earthquake with contributing picks.
- `GET /history/profiles` — profile switch log from `profile_changes`.
- `GET /report/carbon` — counterfactual carbon savings report comparing actual emissions & recall against `always-performance` and `always-eco` baselines.

---

## 5. Kubernetes & Container Conventions

### Deployment & Job Names (Namespace: `quakeshift`)
- Live pickers: `picker-eco`, `picker-balanced`, `picker-performance` (label `app.kubernetes.io/component=picker`, `quakeshift/profile=<profile>`)
- Back-fill jobs: `backfill-<period_id>` (label `app.kubernetes.io/component=backfill`)
- Stateful infrastructure: `kafka`, `postgres`
- Services: `ingestor`, `associator`, `results-api`, `carbon-signal`, `carbon-controller`

### Standard Environment Variables
All Python services read configuration exclusively from environment variables so they run identically in Docker Compose and Kubernetes:

| Variable | Example (Compose) | Example (Kubernetes) | Used By |
| --- | --- | --- | --- |
| `KAFKA_BOOTSTRAP` | `localhost:9092` | `kafka.quakeshift.svc:9092` | ingestor, pickers, backfill, associator |
| `POSTGRES_DSN` | `postgresql://quakeshift:quakeshift@localhost:5432/quakeshift` | `postgresql://...@postgres.quakeshift.svc:5432/quakeshift` | associator, results-api, carbon-controller |
| `PICKER_PROFILE` | `balanced` | `eco` / `balanced` / `performance` | pickers |
| `BACKFILL_START` / `BACKFILL_END` | `2024-05-01T10:00:00Z` | Job env (set by controller) | backfill-job |
| `CORE_STATIONS` | `IV.ATVO,IV.ATMI,IV.ATFO` | ConfigMap for the selected replay | pickers (`eco`) |
| `CARBON_SIGNAL_URL` | `http://localhost:8001` | `http://carbon-signal.quakeshift.svc:8001` | carbon-controller |
| `CONTROLLER_URL` | `http://localhost:8002` | `http://carbon-controller.quakeshift.svc:8002` | results-api |
| `PROMETHEUS_URL` | `http://localhost:9090` | `http://prometheus.quakeshift.svc:9090` | carbon-controller, results-api |
| `METRICS_PORT` | `9100` | `9100` | all services |

For the Tyrol replay, use `OE.SQTA,OE.MOTA,OE.WATA,OE.FETA` for `CORE_STATIONS`.

### Observability & Dashboard Conventions
- **Prometheus pod discovery.** Each service pod includes the scrape annotations `prometheus.io/scrape: "true"`, `prometheus.io/port: "9100"`, and `prometheus.io/path: "/metrics"`.
- **Grafana dashboards.** Keep `ai-pipeline.json` and `system-energy.json` under `monitoring/grafana/dashboards/`. The Grafana manifests load both.

### Required Prometheus Metric Names
- `quakeshift_pipeline_latency_seconds` (Histogram, labels `stage` and `profile`, with finite buckets at 1, 2, 5, 10, 15, 20, 30, 45, 60, 90, and 120 s). Use `stage="end_to_end"` for first P arrival to first live commit, and `stage="after_third_station"` for the diagnostic.
- `quakeshift_picks_total` (Counter, labels: `station`, `phase`, `profile`, `source`)
- `quakeshift_events_total` (Counter, labels: `profile`, `source`)
- `quakeshift_active_profile` (Gauge, label: `profile` — `1` for active, `0` otherwise)
- `quakeshift_carbon_intensity_gco2_kwh` (Gauge, label: `source`)
- `quakeshift_host_energy_kwh_total` (Counter, exported by host-side CodeCarbon exporter)
- `quakeshift_eval_recall` / `quakeshift_eval_precision` / `quakeshift_eval_detection_delay_seconds` (Gauges, label: `profile`, exported by evaluator)
