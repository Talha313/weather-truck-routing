"""Route options from third-party routing engines.

Primary: Valhalla (FOSSGIS public server) with the `truck` costing model, which honours
truck restrictions and truck speeds and takes the vehicle weight into account.
Fallback: the OSRM demo server (car profile) with speeds capped to a truck-realistic 65 mph.

Both engines return *up to* N alternatives and often fewer, but the app must show 3 options.
Missing options are filled by asking the same engine for a route forced through a detour
point to either side of the straight line between origin and destination, keeping only
candidates that are genuinely different and not absurdly long.
"""

import hashlib
import logging
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from django.conf import settings
from django.core.cache import cache

from . import geo
from .http import UpstreamError, session

log = logging.getLogger(__name__)

ROUTE_COUNT = 3
TRUCK_MAX_MPH = 65.0
# Valhalla needs total vehicle weight, the app asks for load weight. A typical empty
# tractor + 53 ft dry van weighs about 35,000 lb.
EMPTY_TRUCK_LBS = 35_000
LBS_PER_TONNE = 2204.62
# Geometry kept for analysis (~20 m tolerance); cumulative miles/times come from full detail.
ANALYSIS_TOLERANCE_DEG = 0.0002
# Detour candidates: (fraction along the straight line, sideways offset as a fraction of it).
DETOURS = ((0.5, 0.12), (0.5, -0.12), (0.5, 0.25), (0.5, -0.25))
MAX_DETOUR_RATIO = 1.6  # reject alternatives > 60% longer than the shortest route
DUPLICATE_OVERLAP = 0.85  # reject alternatives sharing more than 85% of their length


@dataclass
class Route:
    coords: list[geo.LatLon]
    cum_miles: list[float]
    cum_drive_s: list[float]
    via: str
    provider: str

    @property
    def distance_miles(self) -> float:
        return self.cum_miles[-1]

    @property
    def drive_s(self) -> float:
        return self.cum_drive_s[-1]


def _build_route(
    coords: list[geo.LatLon], seg_times: list[float], via: str, provider: str
) -> Route:
    cum_miles = geo.cumulative_miles(coords)
    cum_drive = [0.0]
    for i, t in enumerate(seg_times):
        miles = cum_miles[i + 1] - cum_miles[i]
        # Never faster than a loaded truck would legally drive.
        cum_drive.append(cum_drive[-1] + max(t, miles / TRUCK_MAX_MPH * 3600))
    keep = geo.simplify_indices(coords, ANALYSIS_TOLERANCE_DEG)
    return Route(
        coords=[coords[i] for i in keep],
        cum_miles=[cum_miles[i] for i in keep],
        cum_drive_s=[cum_drive[i] for i in keep],
        via=via,
        provider=provider,
    )


def _via_label(lengths: dict[str, float]) -> str:
    top = sorted(lengths.items(), key=lambda kv: kv[1], reverse=True)[:2]
    return " / ".join(name for name, _ in top)


# ---------------------------------------------------------------- Valhalla


def _valhalla_trip_to_route(trip: dict) -> Route:
    coords: list[geo.LatLon] = []
    seg_times: list[float] = []
    name_lengths: dict[str, float] = defaultdict(float)
    for leg in trip["legs"]:
        shape = geo.decode_polyline(leg["shape"], 6)
        leg_cum = geo.cumulative_miles(shape)
        leg_times = [0.0] * (len(shape) - 1)
        for m in leg["maneuvers"]:
            b, e = m["begin_shape_index"], m["end_shape_index"]
            span = leg_cum[e] - leg_cum[b]
            for i in range(b, e):
                share = (leg_cum[i + 1] - leg_cum[i]) / span if span > 0 else 1 / (e - b)
                leg_times[i] = m["time"] * share
            for name in m.get("street_names", [])[:1]:
                name_lengths[name] += m.get("length", 0.0)
        if coords:  # legs share their joining point; its segments still all count
            shape = shape[1:]
        coords.extend(shape)
        seg_times.extend(leg_times)
    return _build_route(coords, seg_times, _via_label(name_lengths), "valhalla")


def _valhalla(points: list[geo.LatLon], gross_lbs: float, alternates: int) -> list[Route]:
    locations = [{"lat": lat, "lon": lon} for lat, lon in points]
    for loc in locations[1:-1]:
        loc["type"] = "through"
    body = {
        "locations": locations,
        "costing": "truck",
        "costing_options": {"truck": {"weight": round(gross_lbs / LBS_PER_TONNE, 1)}},
        "units": "miles",
        "directions_type": "maneuvers",
        "alternates": alternates,
    }
    try:
        resp = session.post(settings.VALHALLA_URL, json=body, timeout=45)
    except Exception as exc:  # network errors, retries exhausted
        raise UpstreamError(f"Valhalla routing unavailable: {exc}") from exc
    data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
    if resp.status_code != 200 or "trip" not in data:
        raise UpstreamError(data.get("error") or f"Valhalla returned HTTP {resp.status_code}")
    trips = [data["trip"]] + [alt["trip"] for alt in data.get("alternates", [])]
    return [_valhalla_trip_to_route(t) for t in trips]


# ---------------------------------------------------------------- OSRM fallback


def _osrm(points: list[geo.LatLon], gross_lbs: float, alternates: int) -> list[Route]:
    path = ";".join(f"{lon:.6f},{lat:.6f}" for lat, lon in points)
    params = {
        "overview": "full",
        "geometries": "polyline6",
        "annotations": "duration",
        "steps": "true",
        "alternatives": str(alternates) if alternates else "false",
    }
    try:
        resp = session.get(f"{settings.OSRM_URL}/{path}", params=params, timeout=45)
        data = resp.json()
    except Exception as exc:
        raise UpstreamError(f"OSRM routing unavailable: {exc}") from exc
    if data.get("code") != "Ok":
        raise UpstreamError(data.get("message") or "OSRM could not find a route")
    routes = []
    for r in data["routes"]:
        coords = geo.decode_polyline(r["geometry"], 6)
        seg_times = [t for leg in r["legs"] for t in leg["annotation"]["duration"]]
        if len(seg_times) != len(coords) - 1:
            # Fall back to spreading the total duration by distance.
            cum = geo.cumulative_miles(coords)
            total = cum[-1] or 1.0
            seg_times = [r["duration"] * (cum[i + 1] - cum[i]) / total for i in range(len(coords) - 1)]
        via = " / ".join(leg["summary"] for leg in r["legs"] if leg.get("summary"))
        routes.append(_build_route(coords, seg_times, via, "osrm"))
    return routes


# ---------------------------------------------------------------- alternatives


def _bucket(p: geo.LatLon) -> tuple[int, int]:
    return round(p[0] * 20), round(p[1] * 20)  # ~3.5 mile cells


def _overlap(candidate: Route, existing: Route) -> float:
    """Share of the candidate's length lying within ~1.5 miles of the existing route."""
    buckets: dict[tuple[int, int], list[geo.LatLon]] = defaultdict(list)
    for p in geo.resample(existing.coords, existing.cum_miles, 1.0):
        buckets[_bucket(p)].append(p)
    samples = geo.resample(candidate.coords, candidate.cum_miles, 5.0)
    near = 0
    for p in samples:
        by, bx = _bucket(p)
        if any(
            geo.haversine_mi(p, q) <= 1.5
            for dy in (-1, 0, 1)
            for dx in (-1, 0, 1)
            for q in buckets.get((by + dy, bx + dx), ())
        ):
            near += 1
    return near / len(samples)


def _is_distinct(candidate: Route, chosen: list[Route]) -> bool:
    shortest = min(r.distance_miles for r in chosen)
    if candidate.distance_miles > shortest * MAX_DETOUR_RATIO:
        return False
    return all(_overlap(candidate, r) < DUPLICATE_OVERLAP for r in chosen)


def _fill_with_detours(engine, origin, dest, gross_lbs, chosen: list[Route]) -> list[Route]:
    straight = geo.haversine_mi(origin, dest)

    def attempt(detour):
        along, side = detour
        via = geo.offset_point(origin, dest, along, side * straight)
        try:
            return engine([origin, via, dest], gross_lbs, 0)[0]
        except UpstreamError as exc:
            log.info("Detour %s failed: %s", detour, exc)
            return None

    with ThreadPoolExecutor(max_workers=len(DETOURS)) as pool:
        candidates = list(pool.map(attempt, DETOURS))
    for cand in candidates:
        if len(chosen) >= ROUTE_COUNT:
            break
        if cand and _is_distinct(cand, chosen):
            chosen.append(cand)
    return chosen


def get_routes(origin: geo.LatLon, dest: geo.LatLon, load_lbs: float) -> list[Route]:
    gross_lbs = EMPTY_TRUCK_LBS + load_lbs
    key = "routes:" + hashlib.sha1(
        f"{origin[0]:.4f},{origin[1]:.4f}|{dest[0]:.4f},{dest[1]:.4f}|{round(gross_lbs, -3)}".encode()
    ).hexdigest()
    cached = cache.get(key)
    if cached:
        return cached

    engines = [_valhalla, _osrm]
    last_error: Exception | None = None
    for engine in engines:
        try:
            routes = engine([origin, dest], gross_lbs, ROUTE_COUNT - 1)
        except UpstreamError as exc:
            log.warning("%s failed: %s", engine.__name__, exc)
            last_error = exc
            continue
        chosen: list[Route] = []
        for r in routes:
            if not chosen or _is_distinct(r, chosen):
                chosen.append(r)
        if len(chosen) < ROUTE_COUNT:
            chosen = _fill_with_detours(engine, origin, dest, gross_lbs, chosen)
        chosen = chosen[:ROUTE_COUNT]
        cache.set(key, chosen, 60 * 60)
        return chosen
    raise UpstreamError(f"No routing service could find a route: {last_error}")
