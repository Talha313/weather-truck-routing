"""Weather risk heatmap for the trip corridor, hour by hour for 0–48 h after departure.

The corridor is a regular lat/lon grid restricted to cells within ~35 miles of any route.
The grid spacing grows with trip length so a request never needs more than MAX_CELLS
forecasts. Cells are aligned to a global lattice so repeated requests hit the cache.
"""

import math
from datetime import datetime

from . import geo, risk, weather
from .routing import Route

FRAME_HOURS = 48  # frames 0..48 inclusive
MAX_CELLS = 260
MIN_STEP_DEG = 0.2
CORRIDOR_MI = 35.0
MILES_PER_DEG_LAT = 69.0


def _grid(routes: list[Route], step: float) -> tuple[dict, list[tuple[int, int]]]:
    lats = [p[0] for r in routes for p in r.coords]
    lons = [p[1] for r in routes for p in r.coords]
    mid_lat = (min(lats) + max(lats)) / 2
    radius = max(CORRIDOR_MI, step * MILES_PER_DEG_LAT * 0.75)
    pad_lat = radius / MILES_PER_DEG_LAT
    pad_lon = radius / (MILES_PER_DEG_LAT * max(math.cos(math.radians(mid_lat)), 0.2))
    south = math.floor((min(lats) - pad_lat) / step) * step
    west = math.floor((min(lons) - pad_lon) / step) * step
    rows = math.ceil((max(lats) + pad_lat - south) / step)
    cols = math.ceil((max(lons) + pad_lon - west) / step)

    cells: set[tuple[int, int]] = set()
    sample_mi = min(5.0, step * MILES_PER_DEG_LAT / 2)
    for route in routes:
        for lat, lon in geo.resample(route.coords, route.cum_miles, sample_mi):
            r0 = int((lat - south) / step)
            c0 = int((lon - west) / step)
            reach_r = math.ceil(pad_lat / step) + 1
            reach_c = math.ceil(pad_lon / step) + 1
            for r in range(max(0, r0 - reach_r), min(rows, r0 + reach_r + 1)):
                for c in range(max(0, c0 - reach_c), min(cols, c0 + reach_c + 1)):
                    if (r, c) in cells:
                        continue
                    center = (south + (r + 0.5) * step, west + (c + 0.5) * step)
                    if geo.haversine_mi((lat, lon), center) <= radius:
                        cells.add((r, c))
    grid = {"south": round(south, 4), "west": round(west, 4), "step": round(step, 4), "rows": rows, "cols": cols}
    return grid, sorted(cells)


def build_heatmap(routes: list[Route], departure: datetime, load_lbs: float) -> dict:
    step = MIN_STEP_DEG
    grid, cells = _grid(routes, step)
    while len(cells) > MAX_CELLS:
        step *= 1.25
        grid, cells = _grid(routes, step)

    centers = [
        (round(grid["south"] + (r + 0.5) * grid["step"], 3), round(grid["west"] + (c + 0.5) * grid["step"], 3))
        for r, c in cells
    ]
    base = weather.floor_hour(departure)
    series = weather.fetch_series(centers, base, weather.window_hours(FRAME_HOURS))

    scores = []
    for center in centers:
        s = series[center]
        row = []
        for hour in range(FRAME_HOURS + 1):
            c = s.frame(hour)
            row.append(None if c is None else round(risk.risk_score(c.wind_mph, c.rain_in_hr, c.snow_in_hr, load_lbs), 2))
        scores.append(row)

    return {
        "base_time": base.isoformat(),
        "frame_hours": FRAME_HOURS,
        "grid": grid,
        "cells": [list(rc) for rc in cells],
        "scores": scores,
    }
