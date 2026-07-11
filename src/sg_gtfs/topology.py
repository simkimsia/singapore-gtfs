"""Rail service patterns: which stations each line's trains visit, in order.

Sequences are built from the station codes in the concordance (numeric order
within a line prefix), so newly opened stations appear automatically. The
hand-declared parts are the network's shape: the CC orbital loop + Dhoby Ghaut
stub, the Changi branch off EW4, the BP stem + ring, and the LRT petal loops.
"""

from dataclasses import dataclass

from sg_gtfs import concordance

# GTFS route_type: 1 = metro, 0 = tram/light rail.
MRT, LRT = 1, 0


@dataclass(frozen=True)
class Pattern:
    route_id: str
    route_name: str
    route_type: int
    codes: tuple[str, ...]  # visited stations, in order
    circular: bool  # if True, trips return from the last code to the first


def _line(prefix: str) -> list[str]:
    codes = [
        (int(c.removeprefix(prefix)), c)
        for c in concordance.by_code()
        if c.startswith(prefix) and c.removeprefix(prefix).isdigit()
    ]
    return [c for _, c in sorted(codes)]


def patterns() -> tuple[Pattern, ...]:
    cc = _line("CC")
    cc_stub = [c for c in cc if int(c.removeprefix("CC")) <= 4]  # CC1..CC4
    cc_loop = [c for c in cc if int(c.removeprefix("CC")) >= 4]  # CC4..CC34, wraps

    return (
        Pattern("NS", "North-South Line", MRT, tuple(_line("NS")), False),
        Pattern("EW", "East-West Line", MRT, tuple(_line("EW")), False),
        Pattern("CG", "East-West Line Changi Branch", MRT, ("EW4", *_line("CG")), False),
        Pattern("NE", "North East Line", MRT, tuple(_line("NE")), False),
        Pattern("CC", "Circle Line", MRT, tuple(cc_loop), True),
        Pattern("CCE", "Circle Line (Dhoby Ghaut Branch)", MRT, tuple(cc_stub), False),
        Pattern("DT", "Downtown Line", MRT, tuple(_line("DT")), False),
        Pattern("TE", "Thomson-East Coast Line", MRT, tuple(_line("TE")), False),
        Pattern("BP", "Bukit Panjang LRT", LRT, tuple(_line("BP")[:6]), False),  # BP1..BP6
        Pattern("BPL", "Bukit Panjang LRT Loop", LRT, tuple(_line("BP")[5:]), True),
        Pattern("SKE", "Sengkang LRT East Loop", LRT, ("STC", *_line("SE")), True),
        Pattern("SKW", "Sengkang LRT West Loop", LRT, ("STC", *_line("SW")), True),
        Pattern("PGE", "Punggol LRT East Loop", LRT, ("PTC", *_line("PE")), True),
        Pattern("PGW", "Punggol LRT West Loop", LRT, ("PTC", *_line("PW")), True),
    )


def hops(pattern: Pattern) -> list[tuple[str, str]]:
    """Consecutive station-code pairs a trip on this pattern traverses."""
    pairs = list(zip(pattern.codes, pattern.codes[1:]))
    if pattern.circular:
        pairs.append((pattern.codes[-1], pattern.codes[0]))
    return pairs
