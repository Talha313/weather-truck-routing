"""Small, dependency-free geometry helpers. Coordinates are (lat, lon) tuples in degrees."""

import math
from bisect import bisect_right

EARTH_RADIUS_MI = 3958.7613

LatLon = tuple[float, float]


def haversine_mi(a: LatLon, b: LatLon) -> float:
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * EARTH_RADIUS_MI * math.asin(min(1.0, math.sqrt(h)))


def decode_polyline(encoded: str, precision: int = 6) -> list[LatLon]:
    """Decode a Google-style encoded polyline (Valhalla uses precision 6)."""
    coords: list[LatLon] = []
    index = lat = lon = 0
    factor = 10**precision
    length = len(encoded)
    while index < length:
        deltas = []
        for _ in range(2):
            shift = result = 0
            while True:
                byte = ord(encoded[index]) - 63
                index += 1
                result |= (byte & 0x1F) << shift
                shift += 5
                if byte < 0x20:
                    break
            deltas.append(~(result >> 1) if result & 1 else result >> 1)
        lat += deltas[0]
        lon += deltas[1]
        coords.append((lat / factor, lon / factor))
    return coords


def cumulative_miles(coords: list[LatLon]) -> list[float]:
    cum = [0.0]
    for prev, cur in zip(coords, coords[1:]):
        cum.append(cum[-1] + haversine_mi(prev, cur))
    return cum


def locate(cum: list[float], value: float) -> tuple[int, float]:
    """Find segment i and fraction f so that value == cum[i] + f * (cum[i+1] - cum[i])."""
    if value <= cum[0]:
        return 0, 0.0
    if value >= cum[-1]:
        return len(cum) - 2, 1.0
    i = bisect_right(cum, value) - 1
    span = cum[i + 1] - cum[i]
    return i, (value - cum[i]) / span if span > 0 else 0.0


def lerp(a: float, b: float, f: float) -> float:
    return a + (b - a) * f


def point_at(coords: list[LatLon], i: int, f: float) -> LatLon:
    (lat1, lon1), (lat2, lon2) = coords[i], coords[i + 1]
    return lerp(lat1, lat2, f), lerp(lon1, lon2, f)


def simplify_indices(coords: list[LatLon], tolerance_deg: float) -> list[int]:
    """Iterative Ramer-Douglas-Peucker; returns the indices of the points to keep."""
    n = len(coords)
    if n <= 2:
        return list(range(n))
    keep = [False] * n
    keep[0] = keep[-1] = True
    stack = [(0, n - 1)]
    tol2 = tolerance_deg * tolerance_deg
    while stack:
        start, end = stack.pop()
        (ay, ax), (by, bx) = coords[start], coords[end]
        dx, dy = bx - ax, by - ay
        seg2 = dx * dx + dy * dy
        best_i, best_d2 = -1, tol2
        for i in range(start + 1, end):
            py, px = coords[i]
            if seg2 == 0:
                d2 = (px - ax) ** 2 + (py - ay) ** 2
            else:
                t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / seg2))
                d2 = (px - ax - t * dx) ** 2 + (py - ay - t * dy) ** 2
            if d2 > best_d2:
                best_i, best_d2 = i, d2
        if best_i != -1:
            keep[best_i] = True
            stack.append((start, best_i))
            stack.append((best_i, end))
    return [i for i, k in enumerate(keep) if k]


def resample(coords: list[LatLon], cum: list[float], spacing_mi: float) -> list[LatLon]:
    """Points every `spacing_mi` along the line, always including both ends."""
    total = cum[-1]
    points = []
    mile = 0.0
    while mile < total:
        points.append(point_at(coords, *locate(cum, mile)))
        mile += spacing_mi
    points.append(coords[-1])
    return points


def offset_point(origin: LatLon, dest: LatLon, along: float, across_mi: float) -> LatLon:
    """A point `along` (0..1) of the straight line origin→dest, pushed `across_mi`
    perpendicular to it (positive = left of travel direction)."""
    lat = lerp(origin[0], dest[0], along)
    lon = lerp(origin[1], dest[1], along)
    cos_lat = math.cos(math.radians(lat))
    # Work in a local flat frame measured in miles.
    dx = (dest[1] - origin[1]) * 69.172 * cos_lat
    dy = (dest[0] - origin[0]) * 69.0
    norm = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / norm, dx / norm
    return lat + ny * across_mi / 69.0, lon + nx * across_mi / (69.172 * max(cos_lat, 0.01))
