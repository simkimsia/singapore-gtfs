"""Station registry: the one table every other builder module keys off.

SimplyGo's station list is the canonical set of *open* stations (184 as of
extraction — it excludes closed stations like Ten Mile Junction and unopened
ones like DT36). Coordinates come from the DataMall station polygons, with
exit-point centroids as fallback for stations newer than the polygon file
(CCL6, Punggol Coast).
"""

import zipfile
from dataclasses import dataclass
from functools import cache

import geopandas as gpd

from sg_gtfs import raw

@dataclass(frozen=True)
class Station:
    parent_id: str  # e.g. "NS1-EW24"
    name: str  # e.g. "Jurong East"
    codes: tuple[str, ...]  # e.g. ("NS1", "EW24")
    simplygo_id: str  # "" for supplemented stations SimplyGo omits
    lat: float
    lon: float


# Escape hatch for open stations absent from SimplyGo's list. Currently
# empty: the one apparent case (NS15) turned out to be a scrape-parser bug,
# fixed in scripts/extract. Coordinates resolve from the DataMall shapes.
_SUPPLEMENTS: dict[tuple[str, ...], str] = {}


def _normalize(name: str) -> str:
    name = name.upper()
    for suffix in (" MRT STATION", " LRT STATION", " STATION", " INTERCHANGE"):
        name = name.removesuffix(suffix)
    return name.replace("-", " ").replace("'", "").strip()


def _centroids(zip_path) -> dict[str, tuple[float, float]]:
    member = next(n for n in zipfile.ZipFile(zip_path).namelist() if n.endswith(".shp"))
    gdf = gpd.read_file(f"zip://{zip_path}!{member}")
    name_col = next(c for c in gdf.columns if "NAM" in c.upper() and "DE" in c.upper()) \
        if any("NAM_DE" in c.upper() for c in gdf.columns) \
        else next(c for c in gdf.columns if "NAM" in c.upper())
    gdf["_key"] = gdf[name_col].map(_normalize)
    merged = gdf.dissolve(by="_key")
    pts = merged.geometry.centroid.to_frame("geometry").set_geometry("geometry")
    pts = pts.set_crs(merged.crs).to_crs(4326)
    return {key: (geom.y, geom.x) for key, geom in pts.geometry.items()}


@cache
def stations() -> tuple[Station, ...]:
    polygons = _centroids(raw.STATION_POLYGONS)
    exits = _centroids(raw.STATION_EXITS)

    entries = [
        (tuple(row["codes"].split("/")), row["name"].rsplit("[", 1)[0].strip(), row["simplygo_id"])
        for row in raw.read_csv_rows(raw.SIMPLYGO_STATIONS)
        if row["codes"]  # skip scrape artifacts (non-station <option>s)
    ]
    entries += [(codes, name, "") for codes, name in _SUPPLEMENTS.items()]

    result = []
    for codes, name, simplygo_id in entries:
        key = _normalize(name)
        coords = polygons.get(key) or exits.get(key)
        if coords is None:
            raise ValueError(f"no coordinates for station {name!r} (key {key!r})")
        result.append(
            Station(
                parent_id="-".join(codes),
                name=name,
                codes=codes,
                simplygo_id=simplygo_id,
                lat=round(coords[0], 6),
                lon=round(coords[1], 6),
            )
        )
    return tuple(result)


@cache
def by_code() -> dict[str, Station]:
    """Every individual station code (NS1, EW24, STC, …) -> its station."""
    index = {}
    for station in stations():
        for code in station.codes:
            if code in index:
                raise ValueError(f"code {code} maps to two stations")
            index[code] = station
    return index
