"""Hourly forecasts from Open-Meteo (free, no API key), fetched in batches and cached.

Open-Meteo hourly semantics matter for picking the right value at an ETA:
* wind speed / gusts / temperature are instantaneous at the timestamp → interpolate linearly;
* rain / showers / snowfall are totals over the *preceding* hour, i.e. an hourly rate,
  so the rate during (h-1, h] is stamped h → take the value stamped at ceil(t).
Units are requested as mph, inches and °F, so precipitation totals are directly in/hr.
"""

import logging
import math
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from django.conf import settings
from django.core.cache import cache

from .http import UpstreamError, session

log = logging.getLogger(__name__)

VARIABLES = (
    "wind_speed_10m",
    "wind_gusts_10m",
    "rain",
    "showers",
    "snowfall",
    "temperature_2m",
    "weather_code",
)
BATCH_SIZE = 100  # locations per request, keeps URLs well under length limits
PARALLEL_REQUESTS = 4
CACHE_TTL_S = settings.WEATHER_CACHE_TTL_S
# Fetch windows start on 6-hour boundaries, so trips planned within the same block share
# cache entries; each series is then sliced to the hour the caller asked for.
ALIGN_HOURS = 6


@dataclass(frozen=True)
class Conditions:
    wind_mph: float
    gust_mph: float
    rain_in_hr: float
    snow_in_hr: float
    temp_f: float | None
    weather_code: int | None


@dataclass
class Series:
    start: datetime  # UTC, on the hour; index 0
    wind: list
    gust: list
    rain: list  # rain + showers
    snow: list
    temp: list
    code: list

    def __len__(self) -> int:
        return len(self.wind)

    def _conditions(self, wind_i: float, precip_i: int) -> Conditions | None:
        lo, hi = math.floor(wind_i), math.ceil(wind_i)
        f = wind_i - lo
        picks = (self.wind[lo], self.wind[hi], self.gust[lo], self.gust[hi], self.rain[precip_i], self.snow[precip_i])
        if any(v is None for v in picks):
            return None

        def interp(arr):
            a, b = arr[lo], arr[hi]
            return None if a is None or b is None else a + (b - a) * f

        nearest = round(wind_i)
        return Conditions(
            wind_mph=interp(self.wind),
            gust_mph=interp(self.gust),
            rain_in_hr=self.rain[precip_i],
            snow_in_hr=self.snow[precip_i],
            temp_f=interp(self.temp),
            weather_code=self.code[nearest],
        )

    def at(self, t: datetime) -> Conditions | None:
        """Conditions a truck meets at instant t, or None if outside the forecast."""
        x = (t - self.start).total_seconds() / 3600
        if x < 0 or x > len(self) - 1:
            return None
        return self._conditions(x, min(math.ceil(x), len(self) - 1))

    def frame(self, hour: int) -> Conditions | None:
        """Conditions for forecast hour [start+hour, start+hour+1): wind at its start,
        precipitation during it (stamped at its end)."""
        if hour < 0 or hour + 1 > len(self) - 1:
            return None
        return self._conditions(float(hour), hour + 1)

    def slice(self, offset: int, hours: int) -> "Series":
        end = offset + hours
        return Series(
            start=self.start + timedelta(hours=offset),
            wind=self.wind[offset:end],
            gust=self.gust[offset:end],
            rain=self.rain[offset:end],
            snow=self.snow[offset:end],
            temp=self.temp[offset:end],
            code=self.code[offset:end],
        )


def floor_hour(t: datetime) -> datetime:
    return t.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)


def window_hours(needed_hours: float) -> int:
    """Fetch whole days (min 3 = 72 h) so trip and heatmap requests share cache entries."""
    return 24 * max(3, math.ceil((needed_hours + 2) / 24))


def _cache_key(start: datetime, hours: int, point: tuple[float, float]) -> str:
    return f"wx:{start:%Y%m%d%H}:{hours}:{point[0]:.3f},{point[1]:.3f}"


def _parse(item: dict, start: datetime) -> Series:
    h = item["hourly"]

    def add(a, b):
        return [None if x is None or y is None else x + y for x, y in zip(a, b)]

    return Series(
        start=start,
        wind=h["wind_speed_10m"],
        gust=h["wind_gusts_10m"],
        rain=add(h["rain"], h["showers"]),
        snow=h["snowfall"],
        temp=h["temperature_2m"],
        code=h["weather_code"],
    )


def _fetch_batch(points: list[tuple[float, float]], start: datetime, hours: int) -> list[Series]:
    end = start + timedelta(hours=hours - 1)
    params = {
        "latitude": ",".join(f"{lat:.3f}" for lat, _ in points),
        "longitude": ",".join(f"{lon:.3f}" for _, lon in points),
        "hourly": ",".join(VARIABLES),
        "wind_speed_unit": "mph",
        "precipitation_unit": "inch",
        "temperature_unit": "fahrenheit",
        "timezone": "GMT",
        "start_hour": start.strftime("%Y-%m-%dT%H:%M"),
        "end_hour": end.strftime("%Y-%m-%dT%H:%M"),
    }
    try:
        resp = session.get(settings.OPEN_METEO_URL, params=params, timeout=30)
        data = resp.json()
    except Exception as exc:
        log.warning("Open-Meteo request failed: %s", exc)
        raise UpstreamError("Weather service unavailable. Please try again shortly.") from exc
    if resp.status_code == 429:
        reason = data.get("reason") if isinstance(data, dict) else None
        log.warning("Open-Meteo rate limit: %s", reason)
        raise UpstreamError(f"Weather service limit reached ({reason or 'too many requests'}). Please try again later.")
    if resp.status_code != 200:
        reason = data.get("reason") if isinstance(data, dict) else None
        raise UpstreamError(f"Weather service error: {reason or resp.status_code}")
    items = data if isinstance(data, list) else [data]
    return [_parse(item, start) for item in items]


def fetch_series(
    points: list[tuple[float, float]], start: datetime, hours: int
) -> dict[tuple[float, float], Series]:
    """Hourly series starting at `start` (UTC, on the hour) for every distinct point."""
    offset = start.hour % ALIGN_HOURS
    requested_hours = hours
    start, hours = start - timedelta(hours=offset), hours + ALIGN_HOURS
    unique = list(dict.fromkeys(points))
    keys = {p: _cache_key(start, hours, p) for p in unique}
    cached = cache.get_many(list(keys.values()))
    result = {p: cached[k] for p, k in keys.items() if k in cached}
    missing = [p for p in unique if p not in result]
    if missing:
        batches = [missing[i : i + BATCH_SIZE] for i in range(0, len(missing), BATCH_SIZE)]
        with ThreadPoolExecutor(max_workers=PARALLEL_REQUESTS) as pool:
            fetched = list(pool.map(lambda b: _fetch_batch(b, start, hours), batches))
        fresh = {}
        for batch, series_list in zip(batches, fetched):
            for p, series in zip(batch, series_list):
                result[p] = series
                fresh[keys[p]] = series
        cache.set_many(fresh, CACHE_TTL_S)
        log.info("Weather: %d cached, %d fetched in %d requests", len(unique) - len(missing), len(missing), len(batches))
    return {p: s.slice(offset, requested_hours) for p, s in result.items()}
