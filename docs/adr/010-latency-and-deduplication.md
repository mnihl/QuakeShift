# ADR-010 — Live timing and duplicate handling

**Accepted · UC1, UC3**

## Decision

Measure live latency from the first P wave reaching a station to the first database commit. Keep the 60-second target from Assignment 1. Time from the third station helps us understand how quickly the system finishes once it has enough picks.

Kafka can deliver a message again, so consumers confirm it after saving their output. The pipeline identifies waveform windows by ID, merges nearby picks from the same station and phase, and saves one event for overlapping time ranges in each regional run. Back-fill adds evidence to the same event and keeps its original live timing. [Timing and delivery rules](../../CONTRACTS.md#1-timing-and-delivery)

## Alternatives

- Starting at the third station or at ingestion would tell us less about the full delay seen by an operator.
- Requiring shared stations can split one quake into two results when eco and back-fill use different stations.
- Rounded time buckets can split a detection at a bucket boundary. Adding a region to the match makes sense if we later run several regions together.

## Trade-offs

The live timer includes the wait for waves to reach more stations. The time-only duplicate rule can join separate quakes if their padded time ranges overlap. We use one regional replay per result set, and test redelivery and back-fill against both clips.

Recording live and back-fill timing separately lets us compare energy use and how long each mode takes to report an earthquake.
