# QuakeShift

QuakeShift is a **carbon-aware earthquake detection system** for *AI Architecture & Cloud Computing*. It runs pretrained seismic models on open European seismometer data, adapts processing profiles and replica counts to the electricity grid's carbon intensity and latency SLOs, and time-shifts back-fill of eco periods into cleaner grid windows.

**Repository:** <https://github.com/mnihl/QuakeShift>

**Current status.** Recordings reach Kafka, and PhaseNet can identify arrivals in the replay. The associator saves events in PostgreSQL from sample picks. [Project checklist](CHECKLIST.md)

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

## Test the associator locally

With Kafka running in kind, set up PostgreSQL and load the associator image.

```powershell
kubectl --context kind-quakeshift apply -k k8s/postgres
kubectl --context kind-quakeshift -n quakeshift rollout status statefulset/postgres --timeout=300s
docker build -t quakeshift-associator:local associator
kind load docker-image quakeshift-associator:local --name quakeshift
kubectl --context kind-quakeshift apply -f k8s/associator/
kubectl --context kind-quakeshift -n quakeshift rollout status deployment/associator --timeout=120s
```

PostgreSQL loads the schema when it first creates its data directory. After rebuilding and loading the associator image, restart the deployment to use the new image.

Send three made-up P arrivals. After the associator logs an `inserted` event, check for one row with three stations. Start real replay comparisons with fresh results.

```powershell
kubectl --context kind-quakeshift -n quakeshift exec deployment/associator -- python -m associator.sample_picks
kubectl --context kind-quakeshift -n quakeshift exec postgres-0 -- psql -U quakeshift -d quakeshift -c "SELECT first_pick_time, station_count, source FROM events WHERE first_pick_time = '2000-01-01T00:00:00Z';"
```

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
