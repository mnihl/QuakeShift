# QuakeShift

QuakeShift is a **carbon-aware earthquake detection system** for *AI Architecture & Cloud Computing*. It runs pretrained seismic models on open European seismometer data, adapts processing profiles and replica counts to the electricity grid's carbon intensity and latency SLOs, and time-shifts back-fill of eco periods into cleaner grid windows.

**Repository:** <https://github.com/mnihl/QuakeShift>

**Current status.** The local cluster can replay recordings into Kafka. The two replays and laptop CPU benchmark are ready. [Project checklist](CHECKLIST.md)

The planned pipeline uses **CPU-only containers on local Kubernetes (`kind`)** and pretrained models.

`GEOFON replay → ingestor → Kafka → picker → Kafka → associator → PostgreSQL → results API`

Pickers mark P- and S-wave arrival times per station; the associator combines picks across stations into deduplicated earthquake events. A carbon controller switches picker profiles, scales replicas under lag, boosts sensitivity for aftershocks, and schedules green back-fill Jobs.

## Run the Umbertide replay locally

Start Docker Desktop and run `kind create cluster --config kind-config.yaml` if the cluster is new. From the repo folder, deploy Kafka and leave the port-forward running.

```powershell
kubectl --context kind-quakeshift apply -f k8s/base/namespace.yaml
kubectl --context kind-quakeshift apply -f k8s/kafka/
kubectl --context kind-quakeshift -n quakeshift wait --for=condition=complete job/kafka-topics --timeout=300s
kubectl --context kind-quakeshift -n quakeshift port-forward svc/kafka 19092:19092
```

In another PowerShell window, use Python 3.11 and run the sender.

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r ingestor/requirements.txt
.\.venv\Scripts\python scripts/download_replay.py
$env:KAFKA_BOOTSTRAP = "localhost:19092"
.\.venv\Scripts\python -m ingestor.send
```

The first windows go out after 60 seconds. After three minutes, Kafka should acknowledge 78 windows across six stations. For Tyrol, add `tyrol` to the download and sender commands.

## Documentation

- [Project checklist](CHECKLIST.md) for shared tasks and presentation milestones
- [Interface contracts](CONTRACTS.md): Kafka topics/schemas, PostgreSQL DDL, HTTP APIs, K8s conventions, and latency/deduplication definitions
- [Architecture](ARCHITECTURE.md): specification, use cases, components, and diagrams *(updates tracked in checklist)*
- [Architecture decisions (ADRs)](ARCHITECTURE.md#4-architecture-decisions): design choices, alternatives, and sustainability trade-offs
- [Diagram editing guide](docs/architecture/README.md): PlantUML sources and SVG export instructions
- [Local vs server deployment](DEPLOYMENT_COMPARISON.md): deployment trade-offs and the local-first rationale

## Team members

- Morgan Nihlmar (`mnihl`)
- Cristian Vortolomei (`cristianvortolomei`)
