# ADR-004: Switch profiles by scaling Deployments

**Status:** Accepted · **Use cases:** UC2

## Context

When the profile changes, the live pickers must start using a different model. The switch must not lose or skip any waveform window (requirement N5), and the course asks for dynamic redeployment on Kubernetes.

## Decision

Run each profile as its own Kubernetes **Deployment**: `picker-eco`, `picker-balanced`, `picker-performance`. All three join the **same Kafka consumer group**. Only the active one has replicas. To switch, the carbon controller:

1. scales the new profile up and waits until its pods are ready,
2. scales the old profile down to 0,
3. logs the change in PostgreSQL.

Kafka automatically hands the stations (partitions) over to the new pods, starting from the last committed offset.

## Alternatives

| Option | Why not |
| --- | --- |
| One Deployment that swaps the model in memory | No restart, but every pod must load all models (more RAM), and it is not a visible redeployment. |
| Rolling update of one Deployment with a new model setting | Works, but mixes two profiles during the update and is harder to roll back. |
| Kubernetes HPA only | Scales the number of pods, but cannot choose which model runs. |

## Consequences

- ✅ No window is lost or processed twice, thanks to committed offsets.
- ✅ Each profile has its own image settings and CPU/memory limits.
- ✅ The switch is a real, visible Kubernetes redeployment for the demo.
- ❌ For a few seconds both profiles run, until the old one is stopped.
- ❌ Loading a model takes time, so we need a cooldown (no switching back and forth within minutes).

## Sustainability

A profile that is not active has **zero pods**, so it uses no CPU or memory. Eco pods also get smaller CPU limits, which lets the cluster use less of the machine.
