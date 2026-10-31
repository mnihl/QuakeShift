# QuakeShift: local versus server deployment

**Recommendation:** develop locally first, then use a shared server for integration and longer experiments if suitable hardware is readily available. Keep deployment configuration portable between environments. Compare processing modes using the same controlled hardware and recordings. This recommendation remains subject to team review and hardware availability.

Here, **local** means a developer's everyday computer. A **server** is a separate shared machine: university hardware, a home server or a rented virtual machine (VM).

| Consideration | Local computer | Separate server | Implication for QuakeShift |
| --- | --- | --- | --- |
| **Development speed** | Easy debugging, immediate access to files and tools. | Requires remote access and deployment steps. | Local is convenient for building the first working pipeline. |
| **Team collaboration** | The environment depends on whose computer is running. | Both developers can access the same deployment and dashboards. | A server helps the team inspect identical results. |
| **Continuous ingestion** | Sleep, shutdowns and everyday use interrupt experiments. | Can remain running independently of developer activity. | A server is more convenient for overnight ingestion and catch-up experiments. |
| **Hardware capacity** | Limited to existing CPU, RAM and GPU; competes with other applications. | Can provide dedicated resources, but a small rented VM may be weaker than a developer's computer. | Benchmark actual hardware before assuming a server improves performance. |
| **Cost** | Uses existing equipment, plus electricity and storage. | University hardware may be available; rented infrastructure adds recurring costs. | There is little reason to rent infrastructure before measuring requirements. |
| **Energy measurement** | Background applications introduce noise, but physical hardware may expose useful counters. | Dedicated physical hardware can improve experimental control; a shared VM may hide counters and introduce attribution uncertainty. | **Dedicated versus shared hardware matters more than local versus remote.** CodeCarbon measurements depend on available hardware interfaces. [Methodology](https://docs.codecarbon.io/3.3/explanation/methodology/) |
| **Operations** | Easier to keep private; experiments stop when the machine does. | Needs access control, updates, storage management and backups. | A server adds work beyond implementing earthquake detection. |
| **Self-redeployment** | Kubernetes can demonstrate scaling and rolling redeployment locally. | The same mechanisms can run on a server. | A server is **not required** to demonstrate resource awareness or self-redeployment. [Kubernetes Deployments](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/) |
| **Failure resilience** | One machine remains one failure point. | A single server also remains one failure point. | Moving to a server alone does not provide high availability. [Kubernetes guidance](https://kubernetes.io/docs/setup/production-environment/) |

Before choosing a shared server, confirm its CPU/RAM/GPU capacity, availability, access, cost and energy-measurement support.

See the [architecture overview](ARCHITECTURE.md), [architecture alternatives](ARCHITECTURE_COMPARISON.md) and [review checklist](CHECKLIST.md).
