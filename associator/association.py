"""Group picks using their recorded arrival times."""

from datetime import datetime, timedelta

PICK_TOLERANCE = timedelta(seconds=0.5)
P_WINDOW = timedelta(seconds=10)
S_WINDOW = timedelta(seconds=10)
SEARCH_WINDOW = P_WINDOW + S_WINDOW + PICK_TOLERANCE


def arrival(pick):
    return datetime.fromisoformat(pick["pick_time"])


def merge_picks(picks):
    """Keep the strongest pick for repeated arrivals at the same station."""
    merged = []
    for pick in sorted(picks, key=lambda p: (p["station"], p["phase"], arrival(p))):
        previous = merged[-1] if merged else None
        if (
            previous
            and (previous["station"], previous["phase"]) == (pick["station"], pick["phase"])
            and arrival(pick) - arrival(previous) <= PICK_TOLERANCE
        ):
            if pick["probability"] > previous["probability"]:
                merged[-1] = pick
        else:
            merged.append(pick)
    return sorted(merged, key=lambda p: (arrival(p), p["station"], p["phase"]))


def event_picks(picks, incoming):
    """Find a three-station P group that the incoming pick could belong to."""
    unique = merge_picks(picks)
    p_picks = [pick for pick in unique if pick["phase"] == "P"]
    incoming_time = arrival(incoming)
    best = []

    for index, first in enumerate(p_picks):
        end = arrival(first) + P_WINDOW
        by_station = {}
        for pick in p_picks[index:]:
            if arrival(pick) > end:
                break
            station = pick["station"]
            if station not in by_station or pick["probability"] > by_station[station]["probability"]:
                by_station[station] = pick

        if len(by_station) < 3 or len(by_station) <= len(best):
            continue
        station_pick = by_station.get(incoming["station"])
        if station_pick is None:
            continue
        group = sorted(by_station.values(), key=arrival)
        if incoming["phase"] == "P":
            belongs = abs(incoming_time - arrival(station_pick)) <= PICK_TOLERANCE
        else:
            belongs = arrival(station_pick) <= incoming_time <= arrival(group[-1]) + S_WINDOW
        if belongs:
            best = group

    if not best:
        return []

    p_at_station = {pick["station"]: arrival(pick) for pick in best}
    s_end = arrival(best[-1]) + S_WINDOW
    nearby_s = [
        pick for pick in unique
        if pick["phase"] == "S"
        and pick["station"] in p_at_station
        and p_at_station[pick["station"]] <= arrival(pick) <= s_end
    ]
    return sorted(best + nearby_s, key=arrival)
