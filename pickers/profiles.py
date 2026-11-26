"""Eco (STA/LTA + PhaseNet) and Performance (EQTransformer) pickers, plus factory."""

from __future__ import annotations

import os
from collections.abc import Iterable
from typing import Any

import numpy as np
from obspy.signal.trigger import classic_sta_lta

from pickers.phasenet import PhaseNetPicker

EQT_MODEL_VERSION = "eqtransformer-instance-v2"
DEFAULT_STA_LTA_THRESHOLD = 5.0
DEFAULT_CORE_STATIONS = ("IV.ATVO", "IV.ATMI", "IV.ATFO")


def parse_core_stations(raw: str | Iterable[str] | None) -> frozenset[str]:
    if raw is None:
        return frozenset(DEFAULT_CORE_STATIONS)
    items = raw.split(",") if isinstance(raw, str) else raw
    return frozenset(s.strip() for s in items if s.strip())


class EQTransformerPicker(PhaseNetPicker):
    """Runs SeisBench EQTransformer (INSTANCE v2) on 60-second windows (performance & backfill)."""

    def __init__(self, profile: str = "performance", source: str = "live", model: Any = None) -> None:
        if model is None:
            import seisbench.models as sbm

            model = sbm.EQTransformer.from_pretrained("instance", version_str="2")
            model.to("cpu")
            model.eval()
        super().__init__(profile=profile, source=source, model=model)
        self.model_version = EQT_MODEL_VERSION


class EcoPicker:
    """Gates core-station windows with ObsPy classic STA/LTA (1 s / 30 s) before PhaseNet."""

    def __init__(
        self,
        core_stations: str | Iterable[str] | None = None,
        *,
        threshold: float = DEFAULT_STA_LTA_THRESHOLD,
        source: str = "live",
        phasenet: PhaseNetPicker | None = None,
    ) -> None:
        self.profile = "eco"
        self.source = source
        self.core_stations = parse_core_stations(core_stations)
        self.threshold = float(threshold)
        self.phasenet = phasenet if phasenet is not None else PhaseNetPicker(profile="eco", source=source)
        self.model_version = self.phasenet.model_version

    def should_run_model(self, window: dict[str, Any]) -> bool:
        if self.core_stations and window["station"] not in self.core_stations:
            return False
        z = np.asarray(window["channels"]["Z"], dtype=np.float64)
        rate = float(window["sample_rate_hz"])
        nsta, nlta = max(1, int(round(rate))), max(2, int(round(30.0 * rate)))
        if z.size == 0:
            return False
        if z.size <= nlta:
            return True
        cft = classic_sta_lta(z - float(np.mean(z)), nsta, nlta)
        return float(np.max(cft)) >= self.threshold

    def pick_window(
        self,
        window: dict[str, Any],
        *,
        source: str | None = None,
        picked_at: str | None = None,
    ) -> list[dict[str, Any]]:
        if not self.should_run_model(window):
            return []
        return self.phasenet.pick_window(window, source=source or self.source, picked_at=picked_at)


def create_picker(
    profile: str,
    *,
    source: str = "live",
    core_stations: str | Iterable[str] | None = None,
    sta_lta_threshold: float | None = None,
):
    """Build the picker matching `profile` (`eco`, `balanced`, or `performance`)."""
    name = profile.strip().lower()
    if name == "eco":
        raw_core = core_stations if core_stations is not None else os.environ.get("CORE_STATIONS")
        thresh = (
            sta_lta_threshold
            if sta_lta_threshold is not None
            else float(os.environ.get("STA_LTA_THRESHOLD", DEFAULT_STA_LTA_THRESHOLD))
        )
        return EcoPicker(core_stations=raw_core, threshold=thresh, source=source)
    if name == "balanced":
        return PhaseNetPicker(profile="balanced", source=source)
    if name == "performance":
        return EQTransformerPicker(profile="performance", source=source)
    raise ValueError(f"Unknown PICKER_PROFILE {profile!r}; expected eco, balanced, or performance")
