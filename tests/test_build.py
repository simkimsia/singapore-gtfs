import pytest

from sg_gtfs import build, checks


@pytest.fixture(scope="module")
def tables():
    return build.assemble()


def test_structural_gates_pass(tables):
    assert checks.run(tables) == []


def test_every_interchange_pair_has_a_measured_walk(tables):
    assert checks.coverage_warnings(tables) == []


def test_feed_shape(tables):
    assert len(tables["transfers"]) == 70
    assert len(tables["routes"]) > 600  # 14 rail patterns + ~600 bus services
    rail_ids = {f"{r}_{d}" for r in ("NS", "EW", "NE", "CC", "DT", "TE") for d in "01"}
    for f in tables["frequencies"]:
        # Letter-variant buses (36B, 857B, …) are peak-only short trips with
        # genuinely sparse published frequencies — up to ~2 h between runs.
        limit = 1500 if f["trip_id"] in rail_ids else 7200
        assert 120 <= f["headway_secs"] <= limit, f


def test_ns_end_to_end_time_is_plausible(tables):
    times = [st for st in tables["stop_times"] if st["trip_id"] == "NS_0"]
    first, last = times[0]["arrival_time"], times[-1]["arrival_time"]
    span_min = (int(last[:2]) * 60 + int(last[3:5])) - (int(first[:2]) * 60 + int(first[3:5]))
    assert 70 <= span_min <= 85  # Jurong East -> Marina South Pier
