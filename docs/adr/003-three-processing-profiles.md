# ADR-003: Three processing profiles from pretrained models

**Status:** Accepted · **Use cases:** UC1, UC2

## Context

The course does not allow training or fine-tuning. We still need a real trade-off between detection quality and energy, so the system has something to switch between when the grid gets dirty.

## Decision

Use pretrained models from **SeisBench** and the classic **STA/LTA** trigger from ObsPy in three profiles:

| Profile | What runs | Expected cost |
| --- | --- | --- |
| Performance | EQTransformer on all stations | highest |
| Balanced | PhaseNet on all stations | medium |
| Eco | STA/LTA on core stations; PhaseNet only on windows where STA/LTA fires | lowest |

Tuning the STA/LTA threshold and choosing the core stations is configuration, not training.

## CPU benchmark

Intel Core i5-1235U laptop with four CPU threads, SeisBench 0.13.0, PyTorch 2.12.0 CPU, and INSTANCE version 2 weights. Times are the median of three warmed runs on each full three-minute clip with all stations and a batch size of 16. Peak RAM is the Windows process working set across both clips, including Python and the model.

| Model | Samples per channel at 100 Hz | Umbertide (6 stations) | Tyrol (9 stations) | Peak RAM |
| --- | ---: | ---: | ---: | ---: |
| PhaseNet | 3,001 | 0.118 s | 0.149 s | 421 MiB |
| EQTransformer | 6,000 | 0.303 s | 0.418 s | 431 MiB |

Both models found all three reviewed core P arrivals at Umbertide and all four at Tyrol within one second of the reference picks. The first trailing window with enough matches ended about 7–8 seconds after the first reviewed core arrival on each replay.

Publish the latest 60 seconds every 10 seconds. This fits EQTransformer, and SeisBench can run PhaseNet on shorter pieces of the same window. The full pipeline timing and the energy comparison are separate tests.

## Alternatives

| Option | Why not |
| --- | --- |
| One model in all profiles, only fewer stations | Smaller energy difference and nothing to show about model choice. |
| Train or fine-tune our own model | Not allowed in this course, and costly in energy. |
| Two profiles only | Works, but a middle step makes switching less abrupt. |

## Consequences

- ✅ A measurable energy vs quality trade-off without any training.
- ✅ Every profile uses ready-made, published models that are easy to explain.
- ❌ STA/LTA misses weak earthquakes and also fires on noise like trucks; back-fill (ADR-006) recovers part of what eco misses.
- ❌ Whether EQTransformer is really better on our stations must be measured, not assumed.

## Sustainability

This is the core energy lever. Eco runs the neural network only on suspicious windows of fewer stations. We will measure the saving with CodeCarbon (target N4: eco ≥ 50 % less energy per station-hour than performance).
