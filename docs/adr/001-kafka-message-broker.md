# ADR-001: Kafka as the message broker

**Status:** Accepted · **Use cases:** UC1, UC3

## Context

Waveform windows and picks must move between the ingestor, pickers and associator. The services run at different speeds, so we need a buffer between them. For back-fill (UC3) we also need to read the same waveform data again hours later.

## Decision

Use **Apache Kafka** (one broker in KRaft mode, no ZooKeeper) with two topics:

- `waveforms`: one message per 30 s window, key = station, kept for **7 days**
- `picks`: P/S arrival times from all pickers

## Alternatives

| Option | Why not |
| --- | --- |
| RabbitMQ | Deletes a message once it is processed, so back-fill would need a separate waveform archive. |
| Redis Streams | Lighter, but keeps data in memory, so 7 days of waveforms do not fit well. Our fallback if Kafka is too heavy. |
| PostgreSQL as a job queue | We would have to write claiming, retries and timeouts ourselves. |

## Consequences

- ✅ Back-fill is just a second consumer group re-reading the same topic (ADR-006). No extra archive.
- ✅ Consumer groups give us a simple, lossless handover between picker profiles (ADR-004).
- ✅ Kafka lag is a clear, standard backlog metric for the SLO and the controller.
- ❌ Kafka runs on the JVM and needs about 0.5–1 GB RAM, even with a single broker.
- ❌ New concepts to learn: topics, partitions, consumer groups, offsets.

## Sustainability

Kafka is always on, so it uses energy even when idle, and its memory competes with the pickers on our laptops. In exchange we avoid storing waveforms twice and never download data from GEOFON again for back-fill. The 7-day retention limits how much disk the data uses.
