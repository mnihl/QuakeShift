# Project alternatives to QuakeShift — draft

Draft of 13.11.2026 for discussion. Three candidate projects that could replace QuakeShift: **AltText Europa**, **Plenum** and **Scribe** (working name for the transcription service).

Facts about data sources, models and licences for AltText Europa and Plenum come from our ideas document of 24.10.2026. Items marked **(estimate)** or **(to verify)** have not been measured or checked.

## What all three share

Everything below is common, so most of the QuakeShift architecture and ADRs carry over.

- **Constraints:** pretrained models only, CPU only, laptops with 16 GB RAM, local Kubernetes (kind), free and open data.
- **Carbon signal service:** `GET /intensity` from a pluggable source: a scenario file for tests and demos, the Austrian SMARD generation mix as the real signal.
- **Carbon controller:** reads intensity and queue state, picks a profile (performance, balanced, eco), and scales one Deployment per profile. Carbon intensity sets the heaviest profile allowed; a breached SLO can only add replicas or move to a cheaper profile.
- **Green scheduler:** deferrable jobs carry a deadline and run in the cleanest window before it.
- **Storage and operations:** PostgreSQL for results and job state, a queue between services, Prometheus and Grafana, GitHub Actions with a replay test on kind.
- **Delivery rule:** the queue delivers at least once; every write is idempotent on a declared key, so a repeated job overwrites its own row.
- **Energy accounting:** whole-machine energy measured on the host, shared out per pod by CPU time; picker-style per-service numbers shown separately. Reported per unit of work and against an "always performance" baseline.
- **Shared extra features:** operator override of the profile, carbon savings report, real and simulated signal side by side, queue-driven replica scaling, a kill-a-pod test in CI.

## 1. AltText Europa

**Idea.** Millions of digitized heritage images have no text description, which excludes blind and low-vision visitors. The system writes alt text in English and German for Europeana items: immediately when a visitor opens an item, and in bulk for a collection backlog when electricity is clean.

**Actors and use cases.**

| Actor | Use case |
| --- | --- |
| Visitor | Request alt text for one item (urgent) |
| Curator | Submit a collection backlog with a deadline |
| Reviewer | Approve, edit or reject a caption |
| Operator | Override the profile, set thresholds, read the carbon report |
| Europeana API, grid signal source | External systems |

**AI component.** Florence-2-base (0.23 B parameters, MIT licence) for captions. German via an OPUS-MT translation model (licence to verify).

| Profile | What runs |
| --- | --- |
| Performance | Detailed caption at full resolution, plus translation |
| Balanced | Short caption at full resolution, plus translation |
| Eco | Short caption on a downscaled image; translation deferred |

**Carbon-aware behaviour.** Visitor requests are always served, with the profile the grid allows. The backlog waits for clean hours. An **upgrade pass** later redoes eco captions with the performance profile, which is QuakeShift's back-fill idea in a simpler form.

**Data.** Europeana APIs: free, account required, personal key issued instantly with reduced rate limits. Metadata is CC0; images follow each record's rights statement, so the harvester keeps open licences only. About 5,000 thumbnails, roughly 250 MB (estimate), cached as a replay set.

**Components.** Harvester (rights filter) → image cache → job queue → caption service (one Deployment per profile) → translation service → alt-text store and API → review UI. Carbon signal, controller and green scheduler on the side.

**Definitions.**

- **Latency:** request received to response sent, p95, on a cache miss. For the backlog: finished before its deadline, yes or no.
- **Deduplication:** a caption is identified by `(Europeana record ID, language, model version, profile)` with a unique constraint.
- **Quality:** two reviewers rate a 50-item sample per profile. An automated image-to-text similarity score on every caption compares eco with performance; it is an indicator, not proof.

**Example SLOs.** On-demand p95 ≤ 4 s (estimate, benchmark first); backlog of 5,000 items done within 72 h; at least 80 % of the sample rated acceptable in every profile.

**Dashboards.** Items captioned, backlog size and deadline margin, latency, eco-versus-performance similarity, share of work done in clean hours, gCO₂e per caption and gCO₂e avoided by time-shifting.

**Demo.** Replay a windy and a still week of the Austrian signal. The backlog drains in the clean hours while a live visitor request is answered at once.

**Risks.** Caption speed on our CPUs is unmeasured. Quality is partly subjective. Captions of historic or sensitive images can be wrong or biased, so they are labelled machine-generated and pass review. Florence-2 may need `trust_remote_code`, depending on the library version.

## 2. Plenum

**Idea.** Austrian parliamentary debates fill thousands of pages a year. Plenum lets citizens and journalists ask what was said about a topic and answers with verbatim quotes and links to the source.

**Actors and use cases.**

| Actor | Use case |
| --- | --- |
| Citizen or journalist | Ask a question; filter by topic, party and period |
| Editor | Request the weekly topic report |
| Operator | Override the profile, trigger re-indexing, read the carbon report |
| Parliament open-data API, grid signal source | External systems |

**AI component.** Retrieval-augmented generation: a multilingual embedding model in two sizes (licences to verify) and a local language model through Ollama.

| Profile | What runs |
| --- | --- |
| Performance | Top-10 retrieval, answer generated by the larger model |
| Balanced | Top-3 retrieval, answer generated by the small model |
| Eco | Ranked verbatim quotes only, no generation; cached answers reused |

**Carbon-aware behaviour.** Questions are always answered. Embedding new transcripts, re-embedding the corpus and the weekly report wait for clean hours; meanwhile answers come from the older index with a freshness notice.

**Data.** Parlament Österreich open data: 25 datasets under CC BY 4.0, JSON export and API. Optionally the Austrian part of ParlaMint 5.0 (CC BY 4.0). One legislative period is roughly 100–300 MB of text (estimate).

**Components.** Ingestor → chunker → embedding service (batch and query paths) → vector store (pgvector, so PostgreSQL is reused) → retriever and answer service (one Deployment per profile) → web UI. Carbon signal, controller and green scheduler on the side.

**Definitions.**

- **Latency:** question received to full answer sent, p95, reported per profile. **Index freshness:** time from a transcript being published to it being searchable.
- **Deduplication:** a chunk is identified by `(content hash, embedding model version)`; re-ingesting a transcript changes nothing.
- **Quality:** hit rate on about 30 hand-written questions with known source passages, measured per profile. Every generated answer must cite at least one source link.

**Example SLOs.** Quotes-only p95 ≤ 1 s; generated answer p95 ≤ 6 s with the small model (estimate); hit rate ≥ 80 % in eco; new transcript searchable within 24 h.

**Dashboards.** Queries, hit rate, latency, tokens generated, index freshness, chunks embedded per batch, gCO₂e per answer and per 1,000 speeches embedded.

**Demo.** A sitting ends while the grid is dirty. Indexing waits and answers show the freshness notice. When the grid turns clean the batch runs and the notice disappears.

**Risks.** A 7 B model is unlikely to be interactive on our laptops, so plan around the 1.5 B size. German answer quality is untested. The topic is political: quote verbatim, link sources, never rank parties.

## 3. Scribe (transcription service)

**Idea.** Users upload audio (lectures, meetings, interviews) and choose when they need the text. Urgent jobs run now; jobs that can wait run in clean hours and get a better model for the same emissions.

**Actors and use cases.**

| Actor | Use case |
| --- | --- |
| User | Submit audio with a deadline ("now" or "by tomorrow 08:00"); fetch the transcript |
| User | Ask for a better transcript of an earlier job |
| Operator | Override the profile, set a carbon budget per user, read the carbon report |
| Grid signal source | External system |

**AI component.** Pretrained Whisper in several sizes, run on CPU with whisper.cpp (tiny 75 MiB, base 142 MiB, small 466 MiB).

| Profile | What runs |
| --- | --- |
| Performance | Whisper small (medium if the benchmark allows) |
| Balanced | Whisper base |
| Eco | Whisper tiny for urgent jobs; everything deferrable waits |

**Carbon-aware behaviour.** Urgent jobs get the profile the grid allows. Deferrable jobs are scheduled into the cleanest window before their deadline and run with the performance profile. Urgent transcripts made in eco can be upgraded later.

**Data.** Public speech datasets with reference transcripts, for example LibriSpeech (English) and Mozilla Common Voice (German); licences to verify. A few hundred clips, well under 1 GB (estimate). Our own recordings for the demo.

**Components.** Upload API → object store for audio (with a deletion deadline) → job queue → transcription workers (one Deployment per profile) → transcript store and API → small web UI. Carbon signal, controller and green scheduler on the side.

**Definitions.**

- **Latency:** job submitted to transcript stored. Reported as p95 for urgent jobs and as real-time factor (processing time divided by audio length). For deferred jobs: finished before the deadline, yes or no.
- **Deduplication:** a job is identified by `(audio content hash, model version)`; the same file submitted twice returns the stored transcript.
- **Quality:** word error rate against the reference transcripts, per profile. This is the most objective metric of the three projects.

**Example SLOs.** Urgent jobs finish within 2× the audio length (estimate); 100 % of deferred jobs meet their deadline; word error rate in eco at most a fixed margin above performance (set after the benchmark).

**Dashboards.** Jobs by state and profile, queue length and deadline margin, real-time factor, word error rate per profile, share of audio processed in clean hours, gCO₂e per audio minute.

**Demo.** Submit one urgent and one deferrable recording while the grid is dirty. The urgent one returns quickly with the tiny model; the other waits, then comes back visibly more accurate when the grid turns clean.

**Risks.** Larger Whisper sizes are slow on a laptop CPU. Voice is personal data: delete audio after processing, use only public or our own recordings. The story is plainer than the other two.

## Comparison

| | AltText Europa | Plenum | Scribe |
| --- | --- | --- | --- |
| Story | Strong: accessibility | Strong: civic tech | Plain: utility |
| Urgent versus deferrable | Very clear | Clear | Very clear |
| Quality metric | Partly subjective | Objective, small test set | Objective, standard |
| Model exchange | Caption detail and resolution | Generation on or off, model size | Model size |
| Heaviest part on CPU | Caption model, small | Language model, slow | Larger Whisper sizes |
| External dependency | Europeana key and rate limits | Parliament API | None after download |
| Questions we must defend | Caption bias and rights | Political neutrality, hallucination | Privacy of audio |
| Effort to a running pipeline | Low to medium | Medium | Low |

**Recommendation.** AltText Europa first, Plenum second, Scribe as the safe fallback if the benchmark shows the other two are too slow.

## Before deciding

1. Ask the teacher whether changing the project after Assignment 1 is allowed.
2. Benchmark the candidate's model on both laptops: seconds per caption, seconds per answer, or real-time factor.
3. For AltText Europa, request the Europeana key and download the replay set the same day.
