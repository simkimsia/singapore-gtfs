"""Rail hop times from the SimplyGo measurements (docs/SOURCES.md §3).

MRT local hops start from measured adjacent-pair times (keyed by station, so a
hop measured on one line — e.g. City Hall-Raffles Place on NS — also serves
the same physical hop on EW). On lines with clean terminal-to-station profiles,
the local hops are calibrated so cumulative sums match SimplyGo's longer
same-line travel times. Shortcut-prone lines use local 2-4 hop windows as
conservative lower bounds instead. Whole-minute rounding means a sub-minute hop
can read 0; those are floored. Sengkang/Punggol LRT hops use SBS Transit's
published adjacent timings; Bukit Panjang LRT falls back to SimplyGo all-pair
measurements.
"""

import math
from functools import cache
from statistics import median

from sg_gtfs import concordance, raw, topology

MIN_HOP_MINUTES = 0.75  # a 0-min reading is a sub-minute hop, not teleportation
MAX_MRT_HOP_MINUTES = 8.0
LRT_PREFIXES = ("BP", "SE", "SW", "PE", "PW", "STC", "PTC")
PROFILE_CALIBRATED_ROUTES = {"EW", "NE", "TE"}
WINDOW_CALIBRATED_ROUTES = {"NS", "CC", "CG", "DT"}


def _km(code_a: str, code_b: str) -> float:
    by_code = concordance.by_code()
    a, b = by_code[code_a], by_code[code_b]
    dlat = math.radians(b.lat - a.lat)
    dlon = math.radians(b.lon - a.lon) * math.cos(math.radians((a.lat + b.lat) / 2))
    return 6371 * math.hypot(dlat, dlon)


@cache
def _measured() -> dict[tuple[str, str], float]:
    """(parent_id_from, parent_id_to) -> minutes, averaged over directions."""
    by_code = concordance.by_code()
    sums: dict[tuple[str, str], list[float]] = {}
    for row in raw.read_csv_rows(raw.SIMPLYGO_TIMES):
        try:
            a = by_code[row["from_codes"].split("/")[0]].parent_id
            b = by_code[row["to_codes"].split("/")[0]].parent_id
        except KeyError:
            continue  # scrape artifact row
        key = (a, b) if a <= b else (b, a)
        sums.setdefault(key, []).append(float(row["minutes"]))
    return {key: sum(v) / len(v) for key, v in sums.items()}


def _pair_minutes(code_a: str, code_b: str) -> float | None:
    by_code = concordance.by_code()
    a, b = by_code[code_a].parent_id, by_code[code_b].parent_id
    return _measured().get((a, b) if a <= b else (b, a))


def _line_code(codes: str, prefix: str) -> str | None:
    """Return this row's station code for a line prefix, if present."""
    for code in codes.split("/"):
        suffix = code.removeprefix(prefix)
        if suffix != code and suffix.isdigit():
            return code
    return None


def _pattern_code(codes: str, prefix: str, pattern_codes: tuple[str, ...]) -> str | None:
    """Return the row code used by a route pattern, including branch junctions."""
    return _line_code(codes, prefix) or next(
        (code for code in codes.split("/") if code in pattern_codes), None
    )


@cache
def _profiles(prefix: str) -> dict[tuple[str, str], float]:
    """(line_code_from, line_code_to) -> minutes for SimplyGo line profiles."""
    sums: dict[tuple[str, str], list[float]] = {}
    for row in raw.read_csv_rows(raw.SIMPLYGO_TIMES):
        if row["kind"] != f"{prefix}-profile":
            continue
        a = _line_code(row["from_codes"], prefix)
        b = _line_code(row["to_codes"], prefix)
        if a is None or b is None:
            continue
        sums.setdefault((a, b), []).append(float(row["minutes"]))
    return {key: sum(v) / len(v) for key, v in sums.items()}


def _isotonic(values: list[float], weights: list[float]) -> list[float]:
    """Weighted non-decreasing fit using pool-adjacent-violators."""
    blocks: list[list[float | int]] = []
    for i, (value, weight) in enumerate(zip(values, weights)):
        blocks.append([i, i, weight, value * weight])
        while len(blocks) >= 2:
            prev, cur = blocks[-2], blocks[-1]
            if prev[3] / prev[2] <= cur[3] / cur[2]:
                break
            merged = [prev[0], cur[1], prev[2] + cur[2], prev[3] + cur[3]]
            blocks[-2:] = [merged]

    fitted = [0.0] * len(values)
    for start, end, weight, weighted_sum in blocks:
        avg = weighted_sum / weight
        for i in range(int(start), int(end) + 1):
            fitted[i] = avg
    return fitted


def _monotone_cumulative(
    estimates: list[float],
    weights: list[float],
    total: float,
) -> list[float]:
    """Smooth cumulative profile estimates while enforcing a minimum hop."""
    n = len(estimates)
    residual_total = total - MIN_HOP_MINUTES * (n - 1)
    if residual_total <= 0:
        return estimates

    shifted = [v - i * MIN_HOP_MINUTES for i, v in enumerate(estimates)]
    shifted[0] = 0.0
    shifted[-1] = residual_total

    fit_weights = list(weights)
    fit_weights[0] = fit_weights[-1] = 1_000_000.0
    fitted = _isotonic(shifted, fit_weights)
    result = [v + i * MIN_HOP_MINUTES for i, v in enumerate(fitted)]
    result[0] = 0.0
    result[-1] = total
    return result


def _adjacent_hop_minutes(pattern: topology.Pattern) -> list[float]:
    """Measured adjacent-pair baseline for each topology hop."""
    pairs = topology.hops(pattern)
    result: list[float | None] = [None] * len(pairs)
    for i, (a, b) in enumerate(pairs):
        minutes = _pair_minutes(a, b)
        if minutes is not None:
            result[i] = max(MIN_HOP_MINUTES, minutes)

    # A station SimplyGo omits leaves two consecutive unmeasured hops; split
    # the measured through-time across them by distance ratio.
    for i, value in enumerate(result):
        if value is None and i + 1 < len(result) and result[i + 1] is None:
            a, b = pairs[i]
            _, c = pairs[i + 1]
            through = _pair_minutes(a, c)
            if through is not None:
                share = _km(a, b) / (_km(a, b) + _km(b, c))
                result[i] = max(MIN_HOP_MINUTES, through * share)
                result[i + 1] = max(MIN_HOP_MINUTES, through * (1 - share))

    for i, value in enumerate(result):
        if value is None:
            raise ValueError(f"no measured time for hop {pairs[i]} ({pattern.route_id})")
    return result


def _profile_calibrated_hop_minutes(pattern: topology.Pattern) -> list[float] | None:
    """Calibrate adjacent hops to SimplyGo terminal profiles where safe."""
    prefix = pattern.route_id
    if pattern.circular or prefix not in PROFILE_CALIBRATED_ROUTES:
        return None

    profiles = _profiles(prefix)
    start, end = pattern.codes[0], pattern.codes[-1]
    total_estimates = [profiles[key] for key in ((start, end), (end, start)) if key in profiles]
    if not total_estimates:
        return None
    total = median(total_estimates)

    adjacent = _adjacent_hop_minutes(pattern)
    baseline = [0.0]
    for minutes in adjacent:
        baseline.append(baseline[-1] + minutes)
    baseline_total = baseline[-1]

    estimates: list[float] = []
    weights: list[float] = []
    for i, code in enumerate(pattern.codes):
        values = []
        if i == 0:
            values.append(0.0)
        elif (start, code) in profiles:
            values.append(profiles[(start, code)])

        if i == len(pattern.codes) - 1:
            values.append(total)
        elif (end, code) in profiles:
            values.append(total - profiles[(end, code)])

        if values:
            estimates.append(sum(values) / len(values))
            weights.append(float(len(values)))
        else:
            # Should only be needed for future partial profiles; keep the
            # adjacent shape and scale it to the terminal profile total.
            estimates.append(baseline[i] * total / baseline_total)
            weights.append(0.25)

    cumulative = _monotone_cumulative(estimates, weights, total)
    return [
        max(MIN_HOP_MINUTES, cumulative[i + 1] - cumulative[i])
        for i in range(len(cumulative) - 1)
    ]


@cache
def _window_constraints(
    route_id: str, codes: tuple[str, ...], circular: bool
) -> tuple[tuple[tuple[int, ...], float], ...]:
    """Local SimplyGo window constraints as hop-index sets with minute lower bounds."""
    if route_id not in WINDOW_CALIBRATED_ROUTES:
        return ()

    n = len(codes)
    index = {code: i for i, code in enumerate(codes)}
    constraints: dict[tuple[int, ...], float] = {}

    accepted_kinds = {f"{route_id}-window", f"{route_id}-allpair"}
    for row in raw.read_csv_rows(raw.SIMPLYGO_TIMES):
        if row["kind"] not in accepted_kinds:
            continue
        a = _pattern_code(row["from_codes"], route_id, codes)
        b = _pattern_code(row["to_codes"], route_id, codes)
        if a not in index or b not in index:
            continue

        i, j = index[a], index[b]
        if circular:
            forward_gap = (j - i) % n
            reverse_gap = (i - j) % n
            if 2 <= forward_gap <= 4:
                hop_indices = tuple((i + k) % n for k in range(forward_gap))
            elif 2 <= reverse_gap <= 4:
                hop_indices = tuple((i - k - 1) % n for k in range(reverse_gap))
            else:
                continue
        else:
            gap = abs(j - i)
            if not 2 <= gap <= 4:
                continue
            lo, hi = sorted((i, j))
            hop_indices = tuple(range(lo, hi))

        key = tuple(sorted(hop_indices))
        constraints[key] = max(constraints.get(key, 0.0), float(row["minutes"]))

    return tuple(
        sorted(
            constraints.items(),
            key=lambda item: (len(item[0]), max(item[0]), min(item[0])),
        )
    )


def _window_calibrated_hop_minutes(pattern: topology.Pattern, baseline: list[float]) -> list[float] | None:
    """Raise hops until all local SimplyGo windows are satisfied."""
    constraints = _window_constraints(pattern.route_id, pattern.codes, pattern.circular)
    if not constraints:
        return None

    result = list(baseline)
    for _ in range(100):
        changed = False
        for hop_indices, target in constraints:
            current = sum(result[i] for i in hop_indices)
            if current + 1e-9 >= target:
                continue
            # Conservative calibration: only raise estimates, spreading the
            # missing time across the ambiguous window instead of choosing one
            # station pair as the sole cause. Keep individual MRT hops within
            # the existing sanity range; fail loudly if the windows ever
            # require more.
            deficit = target - current
            adjustable = [i for i in hop_indices if result[i] < MAX_MRT_HOP_MINUTES - 1e-9]
            while deficit > 1e-9 and adjustable:
                add = deficit / len(adjustable)
                remaining = []
                used = 0.0
                for i in adjustable:
                    increase = min(add, MAX_MRT_HOP_MINUTES - result[i])
                    result[i] += increase
                    used += increase
                    if result[i] < MAX_MRT_HOP_MINUTES - 1e-9:
                        remaining.append(i)
                deficit -= used
                adjustable = remaining
            if deficit > 1e-9:
                raise ValueError(f"window constraints exceed sane MRT hop bounds for {pattern.route_id}")
            changed = True
        if not changed:
            return result

    raise ValueError(f"window calibration did not converge for {pattern.route_id}")


@cache
def _sbs_lrt_times() -> dict[str, dict[tuple[str, str], float]]:
    """Published adjacent timings from SBS Transit LRT travel-time charts."""
    by_route: dict[str, dict[tuple[str, str], float]] = {}
    for row in raw.read_csv_rows(raw.SBS_LRT_TIMES):
        by_route.setdefault(row["route_id"], {})[(row["from_code"], row["to_code"])] = float(
            row["minutes"]
        )
    return by_route


def _published_lrt_hop_minutes(pattern: topology.Pattern) -> list[float] | None:
    rows = _sbs_lrt_times().get(pattern.route_id)
    if rows is None:
        return None

    times = []
    for hop in topology.hops(pattern):
        try:
            times.append(rows[hop])
        except KeyError as e:
            raise ValueError(
                f"published LRT times do not match topology for {pattern.route_id}: missing {hop}"
            ) from e
    return times


@cache
def _lrt_rate(pattern: topology.Pattern) -> float:
    """Minutes per hop for an LRT pattern, fitted from multi-hop pairs."""
    codes = pattern.codes
    n = len(codes)
    index = {c: i for i, c in enumerate(codes)}
    rates = []
    for i, a in enumerate(codes):
        for b in codes[i + 1 :]:
            gap = index[b] - index[a]
            hop_count = min(gap, n - gap) if pattern.circular else gap
            minutes = _pair_minutes(a, b)
            if minutes and hop_count >= 2:
                rates.append(minutes / hop_count)
    if not rates:
        raise ValueError(f"no multi-hop measurements for {pattern.route_id}")
    return max(MIN_HOP_MINUTES, min(2.0, median(rates)))


def hop_minutes(pattern: topology.Pattern) -> list[float]:
    """Run time for each hop of the pattern, aligned with topology.hops()."""
    published_lrt = _published_lrt_hop_minutes(pattern)
    if published_lrt is not None:
        return published_lrt

    if pattern.codes[0].startswith(LRT_PREFIXES):
        return [_lrt_rate(pattern)] * len(topology.hops(pattern))

    baseline = _adjacent_hop_minutes(pattern)
    calibrated = _profile_calibrated_hop_minutes(pattern)
    if calibrated is not None:
        return calibrated
    calibrated = _window_calibrated_hop_minutes(pattern, baseline)
    if calibrated is not None:
        return calibrated
    return baseline
