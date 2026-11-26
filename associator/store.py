"""Save pending picks and earthquake records in PostgreSQL."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from psycopg.errors import ExclusionViolation
from psycopg.types.json import Jsonb
from psycopg.types.range import Range

from .association import SEARCH_WINDOW, arrival, event_picks, merge_picks


@dataclass
class EventWrite:
    action: str
    event_id: int | None = None
    first_p_wall: datetime | None = None
    third_p_wall: datetime | None = None
    conflicts: tuple = ()


def event_fields(picks):
    first = min(map(arrival, picks))
    last = max(map(arrival, picks))
    window = Range(first - timedelta(seconds=5), last + timedelta(seconds=10))
    stations = sorted({pick["station"] for pick in picks})
    return first, last, window, len(stations), stations, Jsonb(picks)


def overlaps(connection, window):
    return connection.execute(
        """SELECT id, picks FROM events WHERE event_window && %s::tstzrange
           ORDER BY id FOR UPDATE""",
        (window,),
    ).fetchall()


def save_pick(connection, pick, replay_offset):
    for attempt in range(2):
        try:
            with connection.transaction():
                return save_in_transaction(connection, pick, replay_offset)
        except ExclusionViolation:
            if attempt == 1:
                raise


def save_in_transaction(connection, pick, replay_offset):
    # Serialize pick grouping for our single regional array.
    connection.execute("LOCK TABLE association_picks IN SHARE ROW EXCLUSIVE MODE")
    connection.execute("DELETE FROM association_picks WHERE received_at < NOW() - INTERVAL '5 minutes'")
    pick_time = arrival(pick)
    source = pick["source"]
    inserted = connection.execute(
        """INSERT INTO association_picks (source, pick_id, pick_time, payload, replay_offset_s)
           VALUES (%s, %s, %s, %s, %s)
           ON CONFLICT (source, pick_id) DO UPDATE
           SET payload = EXCLUDED.payload, replay_offset_s = EXCLUDED.replay_offset_s,
               received_at = NOW()
           WHERE (EXCLUDED.payload->>'probability')::float >
                 (association_picks.payload->>'probability')::float
           RETURNING pick_id""",
        (source, pick["pick_id"], pick_time, Jsonb(pick), replay_offset),
    ).fetchone()
    if inserted is None:
        return EventWrite("repeated")

    nearby = connection.execute(
        """SELECT payload, replay_offset_s FROM association_picks
           WHERE source = %s AND pick_time BETWEEN %s AND %s""",
        (source, pick_time - SEARCH_WINDOW, pick_time + SEARCH_WINDOW),
    ).fetchall()
    evidence = event_picks([row["payload"] for row in nearby], pick)
    if not evidence:
        return EventWrite("pending")

    fields = event_fields(evidence)
    matches = overlaps(connection, fields[2])
    if len(matches) > 1:
        return EventWrite("overlap_review", conflicts=tuple(row["id"] for row in matches))
    if matches:
        return update_event(connection, matches[0], evidence, source)

    event = connection.execute(
        """INSERT INTO events (first_pick_time, last_pick_time, event_window, station_count,
                               stations, picks, detected_by_profile, source, updated_by)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
        (*fields, pick["profile"], source, source),
    ).fetchone()
    offsets = {row["payload"]["pick_id"]: row["replay_offset_s"] for row in nearby}
    p_picks = [item for item in evidence if item["phase"] == "P"]
    return EventWrite("inserted", event["id"], wall_time(p_picks[0], offsets), wall_time(p_picks[2], offsets))


def update_event(connection, event, evidence, source):
    combined = merge_picks(event["picks"] + evidence)
    if combined == event["picks"]:
        return EventWrite("repeated", event["id"])

    fields = event_fields(combined)
    matches = overlaps(connection, fields[2])
    if len(matches) > 1:
        return EventWrite("overlap_review", conflicts=tuple(row["id"] for row in matches))

    connection.execute(
        """UPDATE events
           SET first_pick_time = %s, last_pick_time = %s, event_window = %s,
               station_count = %s, stations = %s, picks = %s, updated_by = %s, updated_at = NOW()
           WHERE id = %s""",
        (*fields, source, event["id"]),
    )
    return EventWrite("updated", event["id"])


def wall_time(pick, offsets):
    offset = offsets[pick["pick_id"]]
    return None if offset is None else arrival(pick) + timedelta(seconds=offset)
