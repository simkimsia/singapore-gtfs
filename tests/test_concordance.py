from sg_gtfs import concordance


def test_all_stations_resolve():
    stations = concordance.stations()
    assert len(stations) == 184
    assert all(s.lat and s.lon for s in stations)
    assert all(s.simplygo_id for s in stations)
    assert concordance.by_code()["NS15"].name == "Yio Chu Kang"


def test_codes_unique_and_complete():
    index = concordance.by_code()
    # 183 stations, interchanges carry one code per line
    assert len(index) >= 183
    assert {"NS1", "EW24", "STC", "PTC", "CC30", "CC33", "CC34"} <= index.keys()


def test_jurong_east_coordinates():
    je = concordance.by_code()["NS1"]
    assert je.parent_id == "NS1-EW24"
    assert abs(je.lat - 1.333) < 0.01
    assert abs(je.lon - 103.742) < 0.01


def test_ccl6_stations_have_coordinates():
    index = concordance.by_code()
    for code in ("CC30", "CC31", "CC32"):
        s = index[code]
        assert 1.2 < s.lat < 1.5 and 103.6 < s.lon < 104.1
