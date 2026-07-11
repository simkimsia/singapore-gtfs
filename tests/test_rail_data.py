import pytest

from sg_gtfs import headways, rail_times, raw, topology


def test_every_pattern_hop_has_a_time():
    for pattern in topology.patterns():
        times = rail_times.hop_minutes(pattern)
        assert len(times) == len(topology.hops(pattern))
        assert all(0.75 <= t <= 8 for t in times), (pattern.route_id, times)


def test_known_hop_times():
    ns = next(p for p in topology.patterns() if p.route_id == "NS")
    hops = dict(zip(topology.hops(ns), rail_times.hop_minutes(ns)))
    assert hops[("NS1", "NS2")] == pytest.approx(3, abs=1)  # Jurong East-Bukit Batok


@pytest.mark.parametrize(
    ("route_id", "terminal_minutes"),
    [("EW", 81), ("NE", 36), ("TE", 66)],
)
def test_profile_calibrated_routes_match_terminal_profiles(route_id, terminal_minutes):
    pattern = next(p for p in topology.patterns() if p.route_id == route_id)
    assert sum(rail_times.hop_minutes(pattern)) == pytest.approx(terminal_minutes, abs=0.5)


def test_ew_calibration_matches_tuas_link_to_bedok_profile():
    ew = next(p for p in topology.patterns() if p.route_id == "EW")
    times = rail_times.hop_minutes(ew)
    bedok = ew.codes.index("EW5")
    tuas_link = ew.codes.index("EW33")
    assert sum(times[bedok:tuas_link]) == pytest.approx(68, abs=1)


def test_cg_calibration_matches_tanah_merah_to_changi_airport_allpair():
    cg = next(p for p in topology.patterns() if p.route_id == "CG")
    assert sum(rail_times.hop_minutes(cg)) == pytest.approx(11)


def _line_code(codes: str, prefix: str) -> str | None:
    for code in codes.split("/"):
        suffix = code.removeprefix(prefix)
        if suffix != code and suffix.isdigit():
            return code
    return None


@pytest.mark.parametrize("route_id", ["NS", "CC", "DT"])
def test_window_calibrated_routes_do_not_undercut_simplygo_windows(route_id):
    pattern = next(p for p in topology.patterns() if p.route_id == route_id)
    times = rail_times.hop_minutes(pattern)
    index = {code: i for i, code in enumerate(pattern.codes)}
    checked = 0

    for row in raw.read_csv_rows(raw.SIMPLYGO_TIMES):
        if row["kind"] != f"{route_id}-window":
            continue
        a = _line_code(row["from_codes"], route_id)
        b = _line_code(row["to_codes"], route_id)
        if a not in index or b not in index:
            continue

        i, j = index[a], index[b]
        if pattern.circular:
            n = len(pattern.codes)
            forward_gap = (j - i) % n
            reverse_gap = (i - j) % n
            if 2 <= forward_gap <= 4:
                hop_indices = [(i + k) % n for k in range(forward_gap)]
            elif 2 <= reverse_gap <= 4:
                hop_indices = [(i - k - 1) % n for k in range(reverse_gap)]
            else:
                continue
        else:
            lo, hi = sorted((i, j))
            hop_indices = list(range(lo, hi))

        checked += 1
        assert sum(times[k] for k in hop_indices) >= float(row["minutes"]) - 1e-9

    assert checked > 0


def test_dtl_window_calibration_rejects_shortcut_profile():
    dt = next(p for p in topology.patterns() if p.route_id == "DT")
    assert sum(rail_times.hop_minutes(dt)) >= 67


def test_cc_loop_closes_through_bayfront():
    cc = next(p for p in topology.patterns() if p.route_id == "CC")
    assert cc.codes[0] == "CC4" and cc.codes[-1] == "CC34" and cc.circular
    closing = topology.hops(cc)[-1]
    assert closing == ("CC34", "CC4")
    assert rail_times.hop_minutes(cc)[-1] <= 3  # measured via the DT15-DT16 pair


@pytest.mark.parametrize(
    ("route_id", "expected"),
    [
        ("SKE", [2, 1, 1, 1, 2, 3]),
        ("SKW", [2, 1, 1, 1, 1, 1, 1, 1, 3]),
        ("PGE", [3, 1, 1, 1, 1, 1, 1, 2]),
        ("PGW", [2, 1, 1, 1, 1, 1, 1, 3]),
    ],
)
def test_sbs_lrt_rates_match_published_adjacent_timings(route_id, expected):
    pattern = next(p for p in topology.patterns() if p.route_id == route_id)
    assert rail_times.hop_minutes(pattern) == pytest.approx(expected)


def test_bukit_panjang_lrt_rates_are_plausible():
    for pattern in topology.patterns():
        if pattern.route_id in ("BP", "BPL"):
            rate = rail_times.hop_minutes(pattern)[0]
            assert 0.75 <= rate <= 2.0, (pattern.route_id, rate)


def test_headways_cover_every_route():
    h = headways.headway_minutes()
    assert {p.route_id for p in topology.patterns()} <= h.keys()
    assert all(2 <= v <= 25 for v in h.values()), h
    assert h["BPL"] > h["BP"]  # the BP ring is published sparser than the stem


def test_ns15_hops_remain_plausible_after_window_calibration():
    ns = next(p for p in topology.patterns() if p.route_id == "NS")
    hops = dict(zip(topology.hops(ns), rail_times.hop_minutes(ns)))
    assert hops[("NS14", "NS15")] == pytest.approx(8)  # Khatib gap is long
    assert 2 <= hops[("NS15", "NS16")] <= 3
