# ADR-005: Own carbon controller with a simulated signal

**Status:** Accepted · **Use cases:** UC2, UC3

## Context

Something must decide which profile runs, and when back-fill may start. The decision depends on the carbon intensity of the grid and on our SLOs (latency and backlog). For the demo and for repeatable tests, the carbon signal must be controllable.

## Decision

Write a small **carbon controller** service. Every 30 seconds it:

1. reads the carbon intensity from the **carbon signal** service (`GET /intensity`), which replays a **scenario file** (for example: clean morning, dirty evening peak),
2. reads the Kafka lag of the live pickers from Prometheus,
3. chooses a profile from intensity bands (low → performance, medium → balanced, high → eco),
4. **SLO guard:** if the lag keeps growing, it steps up one profile even when the grid is dirty,
5. switches profiles (ADR-004) and starts back-fill when the grid is clean and the lag is low (ADR-006).

A cooldown of a few minutes prevents switching back and forth.

## Alternatives

| Option | Why not |
| --- | --- |
| KEDA or HPA only | They scale replicas based on load, but cannot choose a model or plan back-fill. |
| Real grid data only (e.g. SMARD for Austria) | Not repeatable, and the grid may not change during our demo. We can add it later as a second signal source. |
| Switch profiles by hand | Not carbon-aware. |

## Consequences

- ✅ Simple, explainable rules that we can unit-test.
- ✅ The same scenario always gives the same switches, so tests and the demo are repeatable.
- ❌ It is our own code, so bugs here affect the whole system. It only gets Kubernetes permissions for the picker Deployments and back-fill Jobs.
- ❌ A simulated signal is not real grid data; we label simulated emissions clearly.

## Sustainability

This is where carbon awareness happens: heavy work runs when electricity is cleaner, and the SLO guard makes sure we save energy without breaking the latency target.
