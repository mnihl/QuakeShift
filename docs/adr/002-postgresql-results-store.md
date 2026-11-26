# ADR-002: PostgreSQL for results only

**Status:** Accepted · **Use cases:** UC1, UC2, UC5

## Context

Detected earthquakes and the history of profile changes must be stored so the API, the evaluator and the dashboards can read them. Several services write and read at the same time. A repeated Kafka message must not create a second copy of the same earthquake.

## Decision

Use **PostgreSQL** for `events`, `profile_changes`, and `backfill_periods`. Kafka keeps the waveform data. The associator merges overlapping detections within one regional run. Each event keeps its original detection source and records which source last updated it. [Database schema](../../CONTRACTS.md#3-postgresql-contract) · [Event matching](010-latency-and-deduplication.md)

## Alternatives

| Option | Why not |
| --- | --- |
| SQLite | A single file, awkward when several pods write at the same time. |
| MongoDB | Our data is small and has a fixed structure; we gain nothing from a document store. |
| Store results in Kafka only | Hard to query ("all earthquakes last week") and to update an event after back-fill. |

## Consequences

- ✅ SQL queries for the API and the evaluation.
- ✅ The exclusion constraint keeps overlapping event rows out of the same result set.
- ❌ One more stateful service to run, with a persistent volume.

## Sustainability

The database only holds small result rows, so it needs little CPU, memory and disk. Keeping waveforms out of it avoids storing the same data twice (they stay in Kafka, ADR-001).
