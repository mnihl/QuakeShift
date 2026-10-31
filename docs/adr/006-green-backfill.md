# ADR-006: Green back-fill by re-reading Kafka

**Status:** Accepted · **Use cases:** UC3

## Context

In eco mode we process fewer stations and use a weaker model, so small earthquakes can be missed. We want to find them later, but only when electricity is cleaner.

## Decision

When the grid is clean and the live lag is low, the carbon controller starts a Kubernetes **Job** for the last eco period that has not been back-filled. The job:

1. uses its own consumer group `backfill` and seeks the `waveforms` topic to the start of the eco period,
2. runs **EQTransformer** on all stations for that period,
3. writes the picks to the `picks` topic, marked as `backfill`,
4. marks the period as done in PostgreSQL.

The associator adds missed earthquakes or updates existing ones. The unique event key prevents duplicates (ADR-002).

## Alternatives

| Option | Why not |
| --- | --- |
| No back-fill | Eco would permanently lose small earthquakes. |
| Separate waveform archive (files or object storage) | Stores the data twice and needs its own retention handling. |
| Download the data again from GEOFON | Extra network traffic and depends on the external service. |

## Consequences

- ✅ Eco loses less in the long run, which makes it easier to accept.
- ✅ Uses the same picker code and the same associator path as live detection.
- ❌ Back-fill must happen within the 7-day retention, otherwise the data is gone.
- ❌ Earthquakes found by back-fill arrive late, so they do not count towards the 60 s latency target.

## Sustainability

The heavy model runs when the carbon intensity is low, so the same computation causes fewer emissions. This is time-shifting, the main idea of carbon-aware computing.
