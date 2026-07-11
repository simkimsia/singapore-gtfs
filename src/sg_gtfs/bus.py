"""Assemble the bus half of the feed from the DataMall dumps.

Run times come from differencing per-stop first-bus times — the day's first
departure is one vehicle passing every stop, so its timeline is a measured
schedule (docs/SOURCES.md). Chains break at short-working trips (a later
supplementary bus makes a mid-route stop's "first bus" earlier) and at
missing times; those hops fall back to a distance-time curve fitted from all
cleanly measured hops, so express highway stretches inherit express pace.
Hop runtimes are then multiplied by BUS_RUNTIME_MULTIPLIER as a
daytime-traffic calibration. Headways average the four BusServices frequency
bands.
"""

from bisect import bisect_left
from collections import defaultdict
from functools import cache
from statistics import median

from sg_gtfs import raw
from sg_gtfs.service import SERVICE_ID, SPAN_END_S, SPAN_START_S, hhmmss

# Conservative daytime-traffic adjustment on measured/fallback bus run times
# (in-vehicle time only — rail, walk and wait are untouched). See
# docs/ASSUMPTIONS.md.
BUS_RUNTIME_MULTIPLIER = 1.05

MIN_HOP_S = 30
DEFAULT_HEADWAY_MIN = 15.0  # services whose frequency bands are all unpublished
_CURVE_BINS_KM = (0.3, 0.6, 1.0, 2.0, 3.0, 5.0, 8.0, 100.0)


def _first_bus_minutes(hhmm: str) -> int | None:
    if not hhmm or not hhmm.strip("-0"):
        return None
    hhmm = hhmm.zfill(4)
    minutes = int(hhmm[:2]) * 60 + int(hhmm[2:])
    return minutes + 1440 if minutes < 180 else minutes  # post-midnight wrap


@cache
def _route_stops() -> dict[tuple[str, str], list[dict]]:
    routes = defaultdict(list)
    for row in raw.read_csv_rows(raw.BUS_ROUTES):
        routes[(row["ServiceNo"], row["Direction"])].append(row)
    for stops in routes.values():
        stops.sort(key=lambda r: int(r["StopSequence"]))
    return dict(routes)


def _measured_hops() -> list[tuple[float, float]]:
    """(km, minutes) for every hop with a clean first-bus differencing."""
    hops = []
    for stops in _route_stops().values():
        for a, b in zip(stops, stops[1:]):
            ta, tb = _first_bus_minutes(a["WD_FirstBus"]), _first_bus_minutes(b["WD_FirstBus"])
            km = float(b["Distance"]) - float(a["Distance"])
            if ta is not None and tb is not None and tb >= ta and km > 0:
                hops.append((km, tb - ta))
    return hops


@cache
def _fallback_curve() -> list[tuple[float, float]]:
    """Median minutes per hop, binned by hop distance."""
    binned: dict[int, list[float]] = defaultdict(list)
    for km, minutes in _measured_hops():
        binned[bisect_left(_CURVE_BINS_KM, km)].append(minutes)
    return [
        (_CURVE_BINS_KM[i], median(binned[i]))
        for i in range(len(_CURVE_BINS_KM))
        if binned[i]
    ]


def _fallback_minutes(km: float) -> float:
    curve = _fallback_curve()
    for upper, minutes in curve:
        if km <= upper:
            return minutes
    return curve[-1][1]


def _runtime_adjusted_seconds(seconds: int) -> int:
    if BUS_RUNTIME_MULTIPLIER <= 0:
        raise ValueError("BUS_RUNTIME_MULTIPLIER must be positive")
    return max(MIN_HOP_S, round(seconds * BUS_RUNTIME_MULTIPLIER))


def _hop_seconds(stops: list[dict]) -> list[int]:
    seconds = []
    for a, b in zip(stops, stops[1:]):
        ta, tb = _first_bus_minutes(a["WD_FirstBus"]), _first_bus_minutes(b["WD_FirstBus"])
        km = max(0.0, float(b["Distance"]) - float(a["Distance"]))
        if ta is not None and tb is not None and tb >= ta and (tb > ta or km < 0.8):
            base_seconds = max(MIN_HOP_S, (tb - ta) * 60)
        else:
            base_seconds = max(MIN_HOP_S, round(_fallback_minutes(km) * 60))
        seconds.append(_runtime_adjusted_seconds(base_seconds))
    return seconds


def _headway_minutes(service_rows: list[dict]) -> float:
    midpoints = []
    for row in service_rows:
        for band in ("AM_Peak_Freq", "AM_Offpeak_Freq", "PM_Peak_Freq", "PM_Offpeak_Freq"):
            numbers = [float(n) for n in row[band].split("-") if n.strip().isdigit()]
            if numbers:
                midpoints.append(sum(numbers) / len(numbers))
    return sum(midpoints) / len(midpoints) if midpoints else DEFAULT_HEADWAY_MIN


def stops() -> list[dict]:
    served = {s["BusStopCode"] for stops in _route_stops().values() for s in stops}
    return [
        {
            "stop_id": row["BusStopCode"],
            "stop_name": row["Description"],
            "stop_lat": row["Latitude"],
            "stop_lon": row["Longitude"],
            "location_type": 0,
            "parent_station": "",
        }
        for row in raw.read_csv_rows(raw.BUS_STOPS)
        if row["BusStopCode"] in served  # DataMall lists some stops no service calls at
    ]


def routes() -> list[dict]:
    return [
        {
            "route_id": f"BUS{service}",
            "agency_id": "LTA",
            "route_short_name": service,
            "route_long_name": f"Bus {service}",
            "route_type": 3,
        }
        for service in sorted({s for s, _ in _route_stops()})
    ]


def trips_and_times() -> tuple[list[dict], list[dict], list[dict]]:
    services = defaultdict(list)
    for row in raw.read_csv_rows(raw.BUS_SERVICES):
        services[row["ServiceNo"]].append(row)

    trips, stop_times, frequencies = [], [], []
    for (service, direction), route_stops in sorted(_route_stops().items()):
        trip_id = f"BUS{service}_{direction}"
        trips.append(
            {
                "route_id": f"BUS{service}",
                "service_id": SERVICE_ID,
                "trip_id": trip_id,
                "direction_id": int(direction) - 1,
            }
        )
        t = SPAN_START_S
        hops = _hop_seconds(route_stops)
        for seq, stop in enumerate(route_stops):
            stop_times.append(
                {
                    "trip_id": trip_id,
                    "arrival_time": hhmmss(t),
                    "departure_time": hhmmss(t),
                    "stop_id": stop["BusStopCode"],
                    "stop_sequence": seq + 1,
                }
            )
            if seq < len(hops):
                t += hops[seq]
        frequencies.append(
            {
                "trip_id": trip_id,
                "start_time": hhmmss(SPAN_START_S),
                "end_time": hhmmss(SPAN_END_S),
                "headway_secs": round(_headway_minutes(services.get(service, [])) * 60),
            }
        )
    return trips, stop_times, frequencies
