BEGIN;

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

-- Keep pending picks across restarts so Kafka can acknowledge them safely.
CREATE TABLE IF NOT EXISTS association_picks (
    source          TEXT NOT NULL CHECK (source IN ('live', 'backfill')),
    pick_id         TEXT NOT NULL,
    pick_time       TIMESTAMPTZ NOT NULL,
    received_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    payload         JSONB NOT NULL,
    replay_offset_s DOUBLE PRECISION,
    PRIMARY KEY (source, pick_id)
);

CREATE INDEX IF NOT EXISTS association_picks_by_time ON association_picks (source, pick_time);

COMMIT;
