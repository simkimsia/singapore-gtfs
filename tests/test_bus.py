from sg_gtfs import bus


def test_bus_runtime_multiplier_applies_to_measured_and_fallback_hops(monkeypatch):
    monkeypatch.setattr(bus, "BUS_RUNTIME_MULTIPLIER", 1.05)
    monkeypatch.setattr(bus, "_fallback_minutes", lambda km: 4)

    measured = [
        {"WD_FirstBus": "0500", "Distance": "0.0"},
        {"WD_FirstBus": "0502", "Distance": "0.4"},
    ]
    fallback = [
        {"WD_FirstBus": "-", "Distance": "0.0"},
        {"WD_FirstBus": "-", "Distance": "1.0"},
    ]

    assert bus._hop_seconds(measured) == [126]
    assert bus._hop_seconds(fallback) == [252]
