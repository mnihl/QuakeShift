# QuakeShift — improvements and response to feedback

Written 10.11.2026 as a discussion draft. Nothing here has been applied to the architecture, ADRs or diagrams yet.

## 1. Where we stand

| Milestone | Requirement (course overview) | State |
| --- | --- | --- |
| Assignment 1, 31.10 | Project selected; ADRs and UML diagrams | Submitted. Feedback: models need fixing, two definitions missing, scope too small, contributions uneven. |
| Assignment 2, **21.11** | At least 50 % implemented, deployed to Kubernetes | **Nothing implemented.** No services, manifests, Dockerfiles, tests or CI. 11 days left. |
| Final, presentation **05.12** | CI/CD, observability, carbon metrics, dynamic adaptation, written report | Designed in ADRs only. |

The repository holds documentation only: `ARCHITECTURE.md`, nine ADRs, six PlantUML diagrams, a checklist and a deployment comparison. The four "Before implementation" items in `CHECKLIST.md` are all still open, and they overlap with the teacher's feedback (latency definition, deduplication, energy boundaries, backlog response).

Grading weights to steer by: architecture and docs 35 % (UML 10, ADRs 10, clarity 15), implementation 25 %, sustainability and deployment 25 %, operations 15 %, data handling 5 %. The UML feedback is therefore worth fixing properly, but the largest risk right now is the missing implementation.

## 2. Teacher feedback, point by point

### 2.1 Use case diagram: the `<<include>>` relationship

**What is wrong.** We drew `UC3 Back-fill ..> UC1 Detect earthquakes in near real time : <<include>>`. Include means the base use case *always* executes the *complete* included use case as part of its own flow, and is incomplete without it. Back-fill does not run live detection: it does not read from GEOFON, is not near real time and has no latency target. It only reuses two steps (picking and association).

**Options.**

1. Remove the relationship. Simplest and correct; the reuse is a design fact that the component and class diagrams already show.
2. Factor out the shared behaviour as its own use case, "Pick and associate arrivals", and let both UC1 and UC3 include it. Correct UML, but it adds a use case that no actor cares about.

Recommendation: option 1.

**Related problems the teacher did not list but will likely see next.**

- "Carbon signal" is an actor in the use case diagram and a component inside the cluster in the component diagram. An actor is outside the system. Either the actor is the external *grid carbon-intensity source* (and our carbon-signal service is the adapter to it), or UC2 and UC3 are time-triggered with no carbon actor.
- The user is linked to UC4 and UC5 only. Nobody can influence the carbon behaviour. An operator actor with real use cases (override profile, set thresholds, read the carbon report) fixes this and supports the "more features" request (section 4).
- UC5 is described in the text as adding no structure. Either drop it from the significant use cases or keep it in the diagram only.

### 2.2 Colours

Remove role colours from all UML diagrams (use case, component, class, sequence) and render them monochrome. The colours restate the architecture overview and have no UML meaning. Keep colour only in the informal `overview.svg`, with a legend on the picture itself, and label that picture as an informal overview, not UML.

### 2.3 Component diagram: not UML, mixes static and dynamic

**What is wrong.**

- `componentStyle rectangle`, `queue`, `database` and `actor` shapes are not component notation.
- Arrows are labelled with data that flows ("waveforms in, picks out", "re-read, extra picks", "scale"). That is a data-flow or communication view. Solid, dashed and two-headed arrows are used without defined meaning.
- A UML component diagram shows static structure: components, the interfaces they **provide** (lollipop) and **require** (socket), and dependencies between them. It says nothing about order or runtime behaviour.

**Proposed fix: three separate views.**

| View | Content | Notation |
| --- | --- | --- |
| Component diagram | Ingestor, Picker, Associator, Results API, Carbon Signal, Carbon Controller, Evaluator, plus Kafka, PostgreSQL, Prometheus as components | Provided/required interfaces: `WaveformTopic`, `PickTopic`, `EventStore`, `EventsAPI` (REST), `IntensityAPI` (REST), `Metrics` (`/metrics`), `KubernetesAPI`. Only `<<use>>` dependencies and interface connectors. No actors, no data labels. |
| Deployment diagram (new) | Node: laptop → kind cluster → namespaces. Deployments `picker-eco/balanced/performance`, StatefulSets Kafka and PostgreSQL, Jobs back-fill and evaluator, container images as artifacts | UML nodes and artifacts. This is where "three Deployments, one consumer group, only one has replicas" belongs, and it suits a cloud course. |
| Sequence diagrams | All behaviour: who calls whom, in what order | Already exist; see 2.4. |

One live-picker component realised by three Deployments is a deployment fact, so the component diagram shows one `Picker` component.

### 2.4 Use case details: UC1 trivial, UC2 one-sided

- **UC1** is a linear pipeline and does not need a sequence diagram. Replace `seq-detection` with the scenario that is not obvious: **a picker crashes mid-window**, Kafka redelivers, and the duplicate is absorbed (this also answers the deduplication question and shows N5).
- **UC2** hardcodes "intensity high → eco, scale performance down". The carbon signal can be low or medium too. Redraw it generically: `current` and `target` profile lifelines, an `alt` fragment for the three intensity bands, plus the parts the ADRs describe but the diagram omits: reading the lag from Prometheus, the cooldown check, waiting for readiness before scaling the old profile down, and the failure branch (new pods never become ready → keep the old profile).
- **UC3** omits "mark period as back-filled in PostgreSQL" and the decision of which period to pick.
- In all sequence diagrams Kafka *pushes* to consumers (`k -> pk : window`). Consumers poll; draw the call from the consumer, with a return message.

### 2.5 Class diagram (not criticised yet, same kind of issues)

- Attributes have no types or visibility; only one method per class.
- `CarbonController ..> Picker : switches` is a runtime/deployment relation, not a code dependency. The controller depends on a Kubernetes client and a policy, not on the `Picker` class.
- Missing classes that the design relies on: profile policy (bands, cooldown, SLO guard), carbon-signal client, event repository, back-fill period, STA/LTA trigger, evaluator.
- `Event.origin_time` is misleading: we never locate the earthquake, so this is the earliest pick time. Rename it, or add location (section 4).

### 2.6 Define latency

N1 says "saved within 60 s of the first P wave reaching a station". As written it cannot be measured and probably cannot be met:

- The ingestor cuts 30 s windows, so a P wave at the start of a window waits up to 30 s before anything is sent.
- An event needs three stations. The wave reaches the third station seconds to tens of seconds after the first, depending on station spacing. That delay is physics, not our pipeline.
- "First P wave" is only known after the fact, from our own picks or from EMSC.

**Proposed definition** (to be agreed by both of us):

- **Pipeline latency** (the SLO): `t_commit − t_data`, where `t_data` is the sample time of the latest pick that completed the event, and `t_commit` is the PostgreSQL commit time of the event row. SLO: p95 ≤ 60 s over a 10-minute window, in every profile.
- Break it into stages, each exported as a histogram: acquisition delay, windowing delay, Kafka queue time, inference time, association wait, database write. Timestamps travel in the message headers.
- **Detection delay** (reported, not an SLO): `t_commit −` EMSC origin time. It includes wave travel time and is only a quality indicator.
- In replay mode, state how replay time maps to wall-clock time (replay at 1× speed, timestamps shifted by a fixed offset).
- Replace fixed 30 s windows by overlapping windows (for example 30 s long, 10 s step) to cap the windowing delay. This creates duplicate picks by design, handled in 2.7.

To verify before committing to window sizes: EQTransformer and PhaseNet in SeisBench expect different input lengths (to my knowledge 60 s and 30 s at 100 Hz). Check the SeisBench docs; the `annotate` API may handle windowing for us.

### 2.7 Define message deduplication

Today the only statement is "unique key (rounded origin time and region)" and "no window is lost or processed twice thanks to committed offsets". The second claim is false: Kafka consumer groups give **at-least-once** delivery, so after a crash or a rebalance (every profile switch causes one) windows are processed again. Rounding also fails at bucket edges: 12:00:04.9 and 12:00:05.1 round to different keys.

**Proposed scheme, three levels.**

| Level | Identity | Mechanism |
| --- | --- | --- |
| Waveform window | `(network.station, window_start)` as Kafka key | Idempotent producer in the ingestor. Reprocessing a window is allowed. |
| Pick | `(station, phase)` and pick time within ± 0.5 s | The associator merges picks inside the tolerance and keeps the one with the highest probability. Covers redelivery, overlapping windows and back-fill picks. |
| Event | Overlap in time (± association window) and in contributing stations with an existing event | Upsert in one transaction: update the existing event (add picks, set `updated_by = backfill`) instead of inserting. Enforce with a PostgreSQL exclusion constraint on a time range instead of a rounded key. |

Delivery rule: consumers commit the Kafka offset only **after** their output is durably written. At-least-once delivery plus idempotent writes gives effectively-once results. The associator keeps pending picks in memory, so on restart it must re-read the `picks` topic from a point one association window before its last committed offset.

Document this in a new ADR ("Delivery guarantees and deduplication") and correct ADR-002 and ADR-004.

### 2.8 CodeCarbon does not measure outside containers

We run CodeCarbon inside the pickers and the back-fill job only. Kafka, PostgreSQL, the associator, the API, the controller, Prometheus, Grafana and the Kubernetes control plane are not measured. In eco mode these always-on parts may dominate, so "eco saves 50 %" (N4) could be true for the picker and untrue for the system. `ARCHITECTURE.md` also claims the numbers include idle time, which the current design cannot deliver.

**Options.**

1. **CodeCarbon on the host in machine mode**, as a small exporter outside the cluster, for whole-machine energy. Per-pod shares are then attributed by CPU-seconds from cAdvisor metrics, which Prometheus already scrapes. Cheap and explainable.
2. **Kepler** for per-pod energy. Proper tool, but it needs hardware counters that are usually unavailable in kind on Docker Desktop/WSL2.
3. Keep picker-only numbers and state the boundary. Weakest answer.

Recommendation: option 1, with a written **energy accounting boundary**: what is measured, what is estimated, what is excluded (GEOFON's servers, network, embodied carbon, the laptop screen). To verify on our machines: whether CodeCarbon can read RAPL at all, or falls back to a TDP-based estimate. If it falls back, the numbers are a model driven by CPU load, and the report must say so.

Then restate N4 at system level: energy per station-hour for the **whole cluster**, with the picker share shown separately.

### 2.9 Uneven contributions

Git history: 7 commits by Morgan, 2 by Cristian, all on 31.10, all directly on `main`.

- Check that Cristian's commit email is linked to his GitHub account. If not, GitHub's contributor view does not count his commits at all.
- Split the implementation into owned vertical slices (section 5), each with its own ADRs, diagrams and tests, so the history shows two authors across code *and* documentation.
- Work on branches with pull requests, each reviewed by the other person. Reviews are visible contributions and help with "you must be able to explain every code block".
- Use `Co-authored-by:` trailers for pair work. Track tasks as GitHub issues assigned to a person.

## 3. Design problems found during this review

Not in the teacher's feedback, but they will surface in implementation or in questions at the presentation.

| # | Problem | Suggested change |
| --- | --- | --- |
| 1 | **SLO guard goes the wrong way.** When lag grows, the controller "steps up one profile", which is a heavier model and makes lag worse. | When lag grows: add picker replicas first, and if that is not enough step **down** to a cheaper model. Carbon intensity sets the upper limit of the profile; the SLO can only push towards cheaper or more replicas. |
| 2 | **Association rule ignores geography.** "3 stations within 10 s" only works when stations are within roughly 60–80 km of each other. With 5–10 stations spread across Europe it will rarely fire. | Choose a dense regional station cluster for the demo, or scale the time window by inter-station distance divided by P-wave speed. Decide before picking stations and replay events. |
| 3 | **Overlap during a switch.** Both profiles consume from the same group until the old one is scaled down, so one period is picked by two models. | Accept it, tag every pick with profile and model version, and let pick-level deduplication absorb it. Record this in ADR-004. |
| 4 | **Back-fill bookkeeping is undefined.** Which periods count as eco, how progress is tracked, what happens if the job dies or retention expires first. | Table `backfill_periods` (start, end, status, deadline = start + 7 days). The job is resumable from its committed offset. Alert when a period is close to its deadline. |
| 5 | **Eco ignores non-core stations** but the consumer group still commits their offsets. | Fine, since back-fill seeks by time, but state it explicitly so it does not look like data loss. |
| 6 | **Checklist says "validated UML diagrams".** | The teacher disagrees. Reword once the diagrams are fixed. |
| 7 | **N7 reproducibility** with neural networks on different CPUs is not guaranteed bit for bit. | Define "same" as the same set of events within the pick tolerance. |

## 4. More features

The teacher expects more scope from a two-person team that uses AI assistance. Candidates, ordered by value for the grade against effort. Each adds a use case, at least one ADR and something to show on a dashboard.

| Feature | What it adds | Grading area | Effort |
| --- | --- | --- | --- |
| **A. Real and forecast carbon signal** | Pluggable signal source: scenario file or a public grid API. With a forecast, back-fill is scheduled into the cleanest window before the retention deadline, instead of "now, if clean". | Sustainability, architecture | Medium |
| **B. Carbon savings report** | Counterfactual: emissions of this run compared with "always performance", next to recall lost and recovered by back-fill. Makes the trade-off discussion concrete. | Sustainability trade-offs, report | Low |
| **C. Operator control** | API and small UI: pin or override the profile, change thresholds, see the mode history and the reason for each switch. Gives the human actor real use cases. | Use cases, implementation | Low–medium |
| **D. Aftershock boost** | After a detected event, stations near it are temporarily processed with the stronger model regardless of carbon intensity. A second, quality-driven adaptation that competes with the carbon rule. | Dynamic behaviour, architecture | Medium |
| **E. Fourth profile: quantized or ONNX model** | A cheaper variant of PhaseNet through export and quantization (no training). A real "dynamic model exchange" with a measurable accuracy and energy difference. | AI model integration, sustainability | Medium, needs a benchmark first |
| **F. Model behaviour monitoring** | Per-station pick rate, STA/LTA false-trigger ratio, agreement between live picks and back-fill picks, alerts when a station drifts. | Observability of AI behaviour | Low |
| **G. Two-dimensional scaling** | Lag-driven replica scaling inside a profile, while the controller chooses the model. Needed anyway for problem 1 in section 3. | Deployment strategy | Low–medium |
| **H. Chaos test in CI** | Kill a picker pod during the replay test and assert that no event is lost or duplicated. Proves N5 and the deduplication design. | CI/CD, correctness | Low |
| **I. Event location and map** | Rough epicentre from arrival times, shown on a map. Makes the output a real product and fixes the `origin_time` naming. | Implementation | Medium–high |

Suggested set: **B, C, F, G, H** are cheap and close gaps we already have; **A** and **D** are the two that visibly raise the scope. E and I only if time remains.

## 5. Plan

### Until Assignment 2 (21.11): a walking skeleton on Kubernetes

Goal: the replay path runs end to end on kind, with one profile switch triggered by the scenario file. That is defensible as 50 %.

1. Agree the definitions in 2.6 and 2.7 and the station cluster (section 3, problem 2). Half a day, both.
2. Replay ingestor → Kafka → one picker (PhaseNet) → associator with deduplication → PostgreSQL → results API.
3. Dockerfiles and Kubernetes manifests; Kafka and PostgreSQL as StatefulSets; everything runs on kind.
4. Carbon signal with a scenario file, and a controller that switches between two picker Deployments.
5. `/metrics` on every service, Prometheus scraping. Minimal CI: lint and unit tests.
6. Fix the UML in parallel (2.1 to 2.5) so the corrected models go in with the second submission.

### Until the presentation (05.12)

Third profile and back-fill; energy accounting (2.8); Grafana dashboards; evaluator against EMSC; full CI/CD with the replay and chaos tests; features from section 4; written report and slides.

### Suggested ownership (to discuss)

| Morgan | Cristian |
| --- | --- |
| Platform: manifests, Kafka, PostgreSQL, CI/CD | Data path: ingestor, pickers, associator, deduplication |
| Carbon signal, controller, scaling (features A, G) | Evaluator, model monitoring, aftershock boost (features D, F) |
| Energy accounting and savings report (B) | Results API and operator control (C), chaos test (H) |
| Deployment diagram, sequence UC2 and UC3, ADR updates 004–009 | Use case, component and class diagrams, crash sequence, new deduplication ADR |

Each person reviews the other's pull requests.

## 6. Decisions we need to make

1. Latency definition and window scheme (2.6).
2. Station cluster and association rule (section 3, problem 2).
3. Energy accounting approach (2.8).
4. Which features from section 4 we commit to.
5. Ownership split and the pull-request workflow (2.9, section 5).
