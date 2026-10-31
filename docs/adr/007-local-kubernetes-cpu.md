# ADR-007: Containers on local Kubernetes, CPU only

**Status:** Accepted · **Use cases:** all

## Context

The course requires deployment on Kubernetes and asks us to justify the deployment strategy (containers vs serverless, region, autoscaling). We have two laptops with about 16 GB RAM and no GPU, and no cloud budget.

## Decision

- Package every service as a **container** and run it on a **local Kubernetes cluster** (kind, minikube as a fallback).
- Use **CPUs only**. All models run on CPU.
- Long-running services (ingestor, pickers, associator, API, controller, Kafka, PostgreSQL) are **Deployments/StatefulSets**. Back-fill and evaluation are **Jobs**.
- Scaling is done by the carbon controller (ADR-004, ADR-005), not by a separate autoscaler, so two controllers never change the same Deployment.

## Alternatives

| Option | Why not |
| --- | --- |
| Serverless functions | The pickers read a continuous stream and keep a model loaded; cold starts would break the 60 s target. |
| Docker Compose | Simpler, but has no Deployments or scaling API, so no real dynamic redeployment. |
| Managed cloud Kubernetes | Costs money and is not needed to show the behaviour. We could choose a low-carbon region there, which we cannot do locally. |
| GPU nodes | We have none; the models are small enough for CPU. |

## Consequences

- ✅ Free, runs on our own machines, same manifests would work on a cloud cluster.
- ✅ Full access to the Kubernetes API for redeployment.
- ❌ One machine is a single point of failure; no high availability.
- ❌ Laptops sleep and are shared with other work, so long experiments need care.

## Sustainability

We use hardware we already own instead of renting new servers. CPU-only small models keep power use low. We cannot pick a greener cloud region, so we shift work in **time** (ADR-006) instead of in **space**.
