from datetime import datetime, timedelta

from associator.association import event_picks, merge_picks

START = datetime.fromisoformat("2023-03-09T19:08:00Z")


def pick(station, seconds, phase="P", probability=0.9):
    return {
        "station": station,
        "phase": phase,
        "pick_time": (START + timedelta(seconds=seconds)).isoformat(),
        "probability": probability,
    }


def test_merge_keeps_strongest_arrival_within_half_a_second():
    duplicate = pick("IV.ATVO", 0.5, probability=0.98)
    later = pick("IV.ATVO", 1.1)
    assert merge_picks([later, duplicate, pick("IV.ATVO", 0)]) == [duplicate, later]


def test_three_distinct_p_stations_are_required():
    arrivals = [pick("IV.ATVO", 0), pick("IV.ATVO", 2), pick("IV.ATMI", 3)]
    s_pick = pick("IV.ATFO", 4, phase="S")
    assert event_picks([*arrivals, s_pick], s_pick) == []


def test_match_out_of_order_arrivals_at_ten_second_boundary():
    first = pick("IV.ATVO", 0)
    second = pick("IV.ATMI", 4)
    third = pick("IV.ATFO", 10)
    s_pick = pick("IV.ATMI", 11, phase="S")
    assert event_picks([third, second, s_pick, first], first) == [first, second, third, s_pick]


def test_arrivals_more_than_ten_seconds_apart_do_not_trigger():
    arrivals = [pick("IV.ATVO", 0), pick("IV.ATMI", 4), pick("IV.ATFO", 10.01)]
    assert event_picks(arrivals, arrivals[-1]) == []
