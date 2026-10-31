# ADR-002: PostgreSQL for results only

**Status:** Accepted · **Use cases:** UC1, UC2, UC5

## Context

Detected earthquakes and the history of profile changes must be stored so the API, the evaluator and the dashboards can read them. Several services write and read at the same time. A repeated Kafka message must not create a second copy of the same earthquake.

## Decision

Use **PostgreSQL** with two tables: `events` (earthquakes) and `mode_changes` (time, profile, carbon intensity). Each event has a unique key (rounded origin time and region), and the associator writes with "insert or update". PostgreSQL stores **results only**: no jobs, no queues, no waveforms.

## Alternatives

| Option | Why not |
| --- | --- |
| SQLite | A single file, awkward when several pods write at the same time. |
| MongoDB | Our data is small and has a fixed structure; we gain nothing from a document store. |
| Store results in Kafka only | Hard to query ("all earthquakes last week") and to update an event after back-fill. |

## Consequences

- ✅ SQL queries for the API and the evaluation.
- ✅ The unique key makes repeated messages and back-fill re-runs safe.
- ❌ One more stateful service to run, with a persistent volume.

## Sustainability

The database only holds small result rows, so it needs little CPU, memory and disk. Keeping waveforms out of it avoids storing the same data twice (they stay in Kafka, ADR-001).
