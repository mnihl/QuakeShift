# ADR-003: Three processing profiles from pretrained models

**Status:** Accepted · **Use cases:** UC1, UC2

## Context

The course does not allow training or fine-tuning. We still need a real trade-off between detection quality and energy, so the system has something to switch between when the grid gets dirty.

## Decision

Use pretrained models from **SeisBench** and the classic **STA/LTA** trigger from ObsPy in three profiles:

| Profile | What runs | Expected cost |
| --- | --- | --- |
| Performance | EQTransformer on all stations | highest |
| Balanced | PhaseNet on all stations | medium (PhaseNet is roughly 2–3× faster than EQTransformer on CPU) |
| Eco | STA/LTA on core stations; PhaseNet only on windows where STA/LTA fires | lowest |

Tuning the STA/LTA threshold and choosing the core stations is configuration, not training.

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
