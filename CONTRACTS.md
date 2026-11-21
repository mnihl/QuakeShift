# QuakeShift — Shared Interface Contracts

This document defines the exact boundaries between **Track A** (seismic pipeline, results API, evaluator) and **Track B** (Kubernetes platform, carbon signal, carbon controller, energy accounting, CI/CD). Both tracks build against these contracts so they can develop and test independently, then integrate without rework.

> **Status:** Draft — both teammates should review and sign off before writing service code (see [CHECKLIST.md](CHECKLIST.md)).

---

## 1. Definitions Locked Across Both Tracks

### Latency
- **Pipeline latency (SLO):** `t_db_commit − t_trigger_sample`, where `t_trigger_sample` is the waveform timestamp of the latest pick that completed the event (3rd station) and `t_db_commit` is the PostgreSQL commit timestamp.
  - **Target:** p95 ≤ 60 s over a 10-minute window, in every profile.
  - **Stage breakdown:** timestamps travel in Kafka message headers (`t_ingested`, `t_picked`) so Prometheus histograms track windowing, Kafka queue, inference, association, and DB write latency separately.
  - **Replay clock mapping:** replay runs at `1×` (or configurable `REPLAY_SPEED`) with timestamps shifted by a fixed offset so replay time aligns with wall-clock time during latency calculation.
- **Detection delay (reported, not an SLO):** `t_db_commit − emsc_origin_time`. Includes seismic wave travel time; exported by the evaluator as a quality metric only.

### Deduplication (3 Levels)
Delivery is **at-least-once** across Kafka; consumers commit offsets **only after** their downstream write succeeds.

| Level | Identity | Mechanism |
| --- | --- | --- |
| **1. Waveform window** | Kafka key `"{network}.{station}"`, payload field `window_id = "{network}.{station}:{window_start_iso}"` | Idempotent Kafka producer (`enable.idempotence=true`). Reprocessing a window on crash or profile switch is expected and safe. |
| **2. Pick** | Same `(station, phase)` with `pick_time` within **±0.5 s** | Associator merges matching picks inside its rolling window and keeps the highest `probability`. Covers redelivery, overlapping windows, and back-fill picks. |
| **3. Event** | Overlapping time range (`event_window`) with shared contributing stations | Transactional PostgreSQL upsert guarded by a GiST exclusion constraint on `event_window`. Back-fill updates existing rows (merges picks, sets `updated_by = 'backfill'`) instead of inserting duplicates. |

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

**`waveforms` message** (overlapping windows: default 30 s length, 10 s step; adjust after SeisBench benchmark):
```json
{
  "window_id": "GE.APE:2024-05-01T10:00:00Z",
  "station": "GE.APE",
  "sample_rate_hz": 100,
  "window_start": "2024-05-01T10:00:00.000Z",
  "window_end": "2024-05-01T10:00:30.000Z",
  "channels": {
    "Z": [0.001, -0.002],
    "N": [0.0, 0.001],
    "E": [-0.001, 0.0]
  },
  "ingested_at": "2026-11-21T12:00:00.120Z",
  "replay_offset_s": 0.0
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
  "model_version": "phasenet-original-0.7",
  "source": "live",
  "ingested_at": "2026-11-21T12:00:00.120Z",
  "picked_at": "2026-11-21T12:00:01.450Z"
}
```
- `phase`: `"P"` or `"S"`
- `profile`: `"eco"` | `"balanced"` | `"performance"`
- `source`: `"live"` | `"backfill"`

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

- **Aftershock boost coupling (zero extra network call):** `carbon-controller` queries `events` on its polling loop (`WHERE created_at >= NOW() - INTERVAL '10 minutes' AND updated_by = 'live'`) to trigger or hold the aftershock performance override.

---

## 4. HTTP API Contracts

Every long-running HTTP service exposes:
- `GET /health` → `200 {"status": "ok"}` (Kubernetes liveness probe)
- `GET /ready` → `200 {"status": "ready"}` once models / Kafka / DB are initialized, else `503` (Kubernetes readiness probe — required for safe profile switches)
- `GET /metrics` → Prometheus text format

### `carbon-signal` (Track B · default port `8001`)
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

### `carbon-controller` (Track B · default port `8002`)
- `GET /status` → current profile, active replicas, override state, aftershock-boost state, latest intensity, current lag, pending back-fill count.
- `POST /override` — body: `{"profile": "performance", "duration_minutes": 30, "reason": "operator test"}`
- `DELETE /override` — clears manual override and returns to carbon-governed mode.
- `PUT /thresholds` — body: `{"low_max_gco2_kwh": 150, "high_min_gco2_kwh": 300, "cooldown_seconds": 180}`

### `results-api` (Track A · default port `8000`)
- `GET /` — minimal static HTML/JS operator & results page (shows events, carbon report, current controller status, and calls override/threshold controls).
- `GET /events?since=&until=&profile=&source=` — list detected earthquakes from PostgreSQL.
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
| `CORE_STATIONS` | `GE.APE,GE.SANT,GE.ISP` | ConfigMap | pickers (`eco`) |
| `CARBON_SIGNAL_URL` | `http://localhost:8001` | `http://carbon-signal.quakeshift.svc:8001` | carbon-controller |
| `CONTROLLER_URL` | `http://localhost:8002` | `http://carbon-controller.quakeshift.svc:8002` | results-api |
| `PROMETHEUS_URL` | `http://localhost:9090` | `http://prometheus.quakeshift.svc:9090` | carbon-controller, results-api |
| `METRICS_PORT` | `9100` | `9100` | all services |

### Required Prometheus Metric Names
- `quakeshift_pipeline_latency_seconds` (Histogram, labels: `stage`, `profile`)
- `quakeshift_picks_total` (Counter, labels: `station`, `phase`, `profile`, `source`)
- `quakeshift_events_total` (Counter, labels: `profile`, `source`)
- `quakeshift_active_profile` (Gauge, label: `profile` — `1` for active, `0` otherwise)
- `quakeshift_carbon_intensity_gco2_kwh` (Gauge, label: `source`)
- `quakeshift_host_energy_kwh_total` (Counter, exported by host-side CodeCarbon exporter)
- `quakeshift_eval_recall` / `quakeshift_eval_precision` / `quakeshift_eval_detection_delay_seconds` (Gauges, label: `profile`, exported by evaluator)
