"""Average per-route headways from the archived LTA map fragments.

Each station fragment carries a "Train Service Frequencies" table per
direction (Mon-Fri peak / off-peak). Per the averaging decision in
docs/SOURCES.md, one headway per route pattern: the mean of every peak and
off-peak midpoint on the pages of that pattern's stations. Matching pages by
station code (not folder) keeps distinct service levels distinct — e.g. the
BP LRT stem runs every ~5 min but its ring stations see ~20 min, and blending
them would misprice both. Interchange pages carry tabs for all their lines,
so line values blend slightly at interchanges; MRT headways are close enough
(4-5 min) that this is noise. Stations newer than the fragments (CC30-32)
contribute no pages and inherit their pattern's value.
"""

import re
from functools import cache

from sg_gtfs import raw, topology

_FREQ_SECTION = re.compile(
    r"Train Service Frequencies.*?<tbody>(.*?)</tbody>", re.DOTALL | re.IGNORECASE
)
_WEEKDAY_ROW = re.compile(r"<tr>\s*<td>\s*Mon[^<]*</td>(.*?)</tr>", re.DOTALL)
_NUMBER = re.compile(r"\d+(?:\.\d+)?")


def _page_midpoints(html: str) -> list[float]:
    """Midpoint of every Mon-Fri peak/off-peak frequency range on the page."""
    midpoints = []
    for section in _FREQ_SECTION.findall(html):
        for row in _WEEKDAY_ROW.findall(section):
            for cell in re.findall(r"<td>(.*?)</td>", row, re.DOTALL):
                # Headways are minutes (< 30); the page's duplicated mobile
                # markup can leak peak-period clock times (e.g. "0730") into
                # a matched section — those must not count.
                numbers = [float(n) for n in _NUMBER.findall(cell) if float(n) < 30]
                if numbers:
                    midpoints.append(sum(numbers) / len(numbers))
    return midpoints


@cache
def _midpoints_by_code() -> dict[str, list[float]]:
    """Station code -> that station page's frequency midpoints."""
    result: dict[str, list[float]] = {}
    for page in raw.LTA_MAP_DIR.rglob("*.html"):
        midpoints = _page_midpoints(page.read_text())
        for code in page.stem.split("-"):
            result[code] = midpoints
    return result


@cache
def headway_minutes() -> dict[str, float]:
    """route_id -> average headway in minutes."""
    by_code = _midpoints_by_code()
    result = {}
    for pattern in topology.patterns():
        midpoints = [m for code in pattern.codes for m in by_code.get(code, [])]
        if not midpoints:
            raise ValueError(f"no frequency data for {pattern.route_id}")
        result[pattern.route_id] = round(sum(midpoints) / len(midpoints), 1)
    return result
