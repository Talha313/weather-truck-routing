"""Builds the full trip analysis: routes → checkpoints with ETAs → weather → risk → ranking."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from . import geo, hos, recommend, risk, weather
from .routing import Route, get_routes

ROUTE_LETTERS = "ABC"
# Checkpoints are snapped to this grid (~3.5 mi) for weather lookups so overlapping
# routes share forecasts; the models behind Open-Meteo are 3–13 km resolution anyway.
WEATHER_SNAP_DEG = 0.05
# Display geometry tolerance (~100 m) keeps the payload small without visible change.
DISPLAY_TOLERANCE_DEG = 0.001


@dataclass
class Checkpoint:
    mile: float
    lat: float
    lon: float
    drive_s: float
    elapsed_s: float
    covers: tuple[float, float]  # route miles this checkpoint represents
    conditions: weather.Conditions | None = None
    assessment: risk.Assessment | None = None


def snap(lat: float, lon: float) -> tuple[float, float]:
    return (
        round(round(lat / WEATHER_SNAP_DEG) * WEATHER_SNAP_DEG, 3),
        round(round(lon / WEATHER_SNAP_DEG) * WEATHER_SNAP_DEG, 3),
    )


def sample_checkpoints(route: Route, interval_mi: float, include_hos: bool) -> list[Checkpoint]:
    """A checkpoint at the origin, every `interval_mi`, and at the destination. Each
    checkpoint represents the route miles closer to it than to its neighbours."""
    total = route.distance_miles
    miles = [i * interval_mi for i in range(int(total // interval_mi) + 1)]
    if total - miles[-1] > 0.05:
        miles.append(total)
    checkpoints = []
    for k, mile in enumerate(miles):
        i, f = geo.locate(route.cum_miles, mile)
        lat, lon = geo.point_at(route.coords, i, f)
        drive_s = geo.lerp(route.cum_drive_s[i], route.cum_drive_s[i + 1], f)
        start = 0.0 if k == 0 else (miles[k - 1] + mile) / 2
        end = total if k == len(miles) - 1 else (mile + miles[k + 1]) / 2
        checkpoints.append(
            Checkpoint(
                mile=mile,
                lat=lat,
                lon=lon,
                drive_s=drive_s,
                elapsed_s=hos.elapsed_for_drive(drive_s, include_hos),
                covers=(start, end),
            )
        )
    return checkpoints


def summarize(checkpoints: list[Checkpoint], travel_s: float) -> tuple[list[float], float, recommend.RouteScore]:
    """Miles per risk level, unknown miles, and the score used for ranking."""
    level_miles = [0.0] * len(risk.LEVEL_NAMES)
    unknown = 0.0
    for cp in checkpoints:
        miles = cp.covers[1] - cp.covers[0]
        if cp.assessment is None:
            unknown += miles
        else:
            level_miles[cp.assessment.level] += miles
    known = sum(level_miles)
    avg = sum(level * m for level, m in enumerate(level_miles)) / known if known else 0.0
    score = recommend.RouteScore(
        no_travel_miles=level_miles[risk.NO_TRAVEL],
        severe_miles=level_miles[risk.SEVERE],
        high_miles=level_miles[risk.HIGH],
        avg_risk=avg,
        travel_s=travel_s,
    )
    return level_miles, unknown, score


def plan_trip(
    origin: dict,
    destination: dict,
    departure: datetime,
    load_lbs: float,
    interval_mi: int,
    include_hos: bool,
) -> dict:
    routes = get_routes((origin["lat"], origin["lon"]), (destination["lat"], destination["lon"]), load_lbs)

    per_route = []
    for route in routes:
        cps = sample_checkpoints(route, interval_mi, include_hos)
        travel_s = hos.elapsed_for_drive(route.drive_s, include_hos)
        per_route.append((route, cps, travel_s))

    start = weather.floor_hour(departure)
    longest_h = (departure - start).total_seconds() / 3600 + max(t for _, _, t in per_route) / 3600
    hours = weather.window_hours(max(longest_h, 48))
    all_points = [snap(cp.lat, cp.lon) for _, cps, _ in per_route for cp in cps]
    series = weather.fetch_series(all_points, start, hours)

    summaries = []
    for route, cps, travel_s in per_route:
        for cp in cps:
            cp.conditions = series[snap(cp.lat, cp.lon)].at(departure + timedelta(seconds=cp.elapsed_s))
            if cp.conditions:
                c = cp.conditions
                cp.assessment = risk.assess(c.wind_mph, c.rain_in_hr, c.snow_in_hr, load_lbs)
        summaries.append(summarize(cps, travel_s))

    scores = [s[2] for s in summaries]
    order = recommend.rank(scores)
    best = order[0]
    names = [f"Route {ROUTE_LETTERS[i]}" for i in range(len(routes))]
    reasons = [
        recommend.explain(scores[best], names[best], scores[i], names[i]) for i in order[1:]
    ]
    all_blocked = all(s.no_travel_miles > 0 for s in scores)

    return {
        "origin": origin,
        "destination": destination,
        "departure_time": departure.isoformat(),
        "load_weight_lbs": load_lbs,
        "checkpoint_interval_miles": interval_mi,
        "include_hos": include_hos,
        "provider": routes[0].provider,
        "recommendation": {
            "route_id": names[best],
            "ranking": [names[i] for i in order],
            "reasons": reasons,
            "warning": (
                "Every route crosses No Travel conditions. Consider delaying departure."
                if all_blocked
                else None
            ),
        },
        "routes": [
            _serialize_route(names[i], ROUTE_LETTERS[i], routes[i], per_route[i][1], per_route[i][2],
                             summaries[i], departure, include_hos, rank=order.index(i) + 1)
            for i in range(len(routes))
        ],
    }


def _serialize_route(name, letter, route: Route, cps, travel_s, summary, departure, include_hos, rank):
    level_miles, unknown, score = summary
    keep = geo.simplify_indices(route.coords, DISPLAY_TOLERANCE_DEG)
    eta = departure + timedelta(seconds=travel_s)
    return {
        "id": name,
        "letter": letter,
        "rank": rank,
        "recommended": rank == 1,
        "via": route.via,
        "distance_miles": round(route.distance_miles, 1),
        "drive_hours": round(route.drive_s / 3600, 2),
        "travel_hours": round(travel_s / 3600, 2),
        "arrival_time": eta.isoformat(),
        "risk_miles": {risk.LEVEL_NAMES[lv]: round(m, 1) for lv, m in enumerate(level_miles)},
        "unknown_miles": round(unknown, 1),
        "avg_risk": round(score.avg_risk, 3),
        "max_level": max((cp.assessment.level for cp in cps if cp.assessment), default=None),
        # [lat, lon, route mile, driving seconds] per point.
        "geometry": [
            [round(route.coords[i][0], 5), round(route.coords[i][1], 5),
             round(route.cum_miles[i], 2), round(route.cum_drive_s[i])]
            for i in keep
        ],
        "stops": [
            {
                "kind": stop.kind,
                "mile": round(_mile_at_drive(route, stop.drive_s), 1),
                "position": _position_at_drive(route, stop.drive_s),
                "start_time": (departure + timedelta(seconds=stop.elapsed_s)).isoformat(),
                "duration_hours": stop.duration_s / 3600,
            }
            for stop in hos.stops_for_trip(route.drive_s, include_hos)
        ],
        "checkpoints": [_serialize_checkpoint(k, cp, departure) for k, cp in enumerate(cps)],
    }


def _serialize_checkpoint(index: int, cp: Checkpoint, departure: datetime) -> dict:
    c, a = cp.conditions, cp.assessment
    return {
        "index": index,
        "mile": round(cp.mile, 1),
        "lat": round(cp.lat, 5),
        "lon": round(cp.lon, 5),
        "covers": [round(cp.covers[0], 2), round(cp.covers[1], 2)],
        "eta": (departure + timedelta(seconds=cp.elapsed_s)).isoformat(),
        "elapsed_hours": round(cp.elapsed_s / 3600, 2),
        "weather": None if c is None else {
            "wind_mph": round(c.wind_mph, 1),
            "gust_mph": round(c.gust_mph, 1),
            "rain_in_hr": round(c.rain_in_hr, 3),
            "snow_in_hr": round(c.snow_in_hr, 3),
            "temp_f": None if c.temp_f is None else round(c.temp_f),
            "weather_code": c.weather_code,
        },
        "risk": None if a is None else {
            "level": a.level,
            "name": a.name,
            "factor": a.factor,
            "wind": a.wind_level,
            "rain": a.rain_level,
            "snow": a.snow_level,
            "load_rule": a.load_rule,
        },
    }


def _drive_index(route: Route, drive_s: float) -> tuple[int, float]:
    return geo.locate(route.cum_drive_s, drive_s)


def _mile_at_drive(route: Route, drive_s: float) -> float:
    i, f = _drive_index(route, drive_s)
    return geo.lerp(route.cum_miles[i], route.cum_miles[i + 1], f)


def _position_at_drive(route: Route, drive_s: float) -> list[float]:
    lat, lon = geo.point_at(route.coords, *_drive_index(route, drive_s))
    return [round(lat, 5), round(lon, 5)]
