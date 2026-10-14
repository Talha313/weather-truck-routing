"""Weather risk classification, implementing the assessment's threshold table and load rules.

Levels are ordered integers so they can be compared and averaged:
    0 Low · 1 Moderate · 2 High · 3 Severe · 4 No Travel

Band edges. The table's printed ranges share their endpoints (e.g. rain "0.10–0.25" and
"0.25–0.50"), so each band includes its lower edge and excludes its upper edge, except
where the table says otherwise: rain and snow only reach No Travel when *strictly above*
1.00 / 3.00, while wind reaches No Travel *at* 55 mph ("≥55").
"""

from dataclasses import dataclass

LOW, MODERATE, HIGH, SEVERE, NO_TRAVEL = range(5)
LEVEL_NAMES = ["Low", "Moderate", "High", "Severe", "No Travel"]

# Lower edges of Moderate, High, Severe, No Travel.
WIND_EDGES_MPH = (25.0, 35.0, 45.0, 55.0)
RAIN_EDGES_IN_HR = (0.10, 0.25, 0.50, 1.00)
SNOW_EDGES_IN_HR = (0.5, 1.0, 2.0, 3.0)

# Load rules.
HEAVY_LOAD_NO_TRAVEL_LBS = 30_000  # 45–54 mph + >30,000 lb → No Travel
HEAVY_LOAD_SEVERE_LBS = 40_000  # 35–44 mph + >40,000 lb → Severe


def _band(value: float, edges: tuple[float, ...], strict_top: bool) -> tuple[int, float]:
    """Return (level, fraction through that level's band in [0, 1))."""
    value = max(0.0, value)
    lowers = (0.0, *edges)
    for level in range(4, 0, -1):
        edge = lowers[level]
        reached = value > edge if (level == 4 and strict_top) else value >= edge
        if reached:
            if level == 4:
                return level, 0.0
            upper = lowers[level + 1]
            return level, min((value - edge) / (upper - edge), 0.99)
    return 0, min(value / edges[0], 0.99)


def wind_level(mph: float) -> int:
    return _band(mph, WIND_EDGES_MPH, strict_top=False)[0]


def rain_level(in_hr: float) -> int:
    return _band(in_hr, RAIN_EDGES_IN_HR, strict_top=True)[0]


def snow_level(in_hr: float) -> int:
    return _band(in_hr, SNOW_EDGES_IN_HR, strict_top=True)[0]


def load_adjusted_wind_level(mph: float, load_lbs: float) -> tuple[int, str | None]:
    """Apply the load rules on top of the wind table. Returns (level, rule applied)."""
    level = wind_level(mph)
    if level == SEVERE and load_lbs > HEAVY_LOAD_NO_TRAVEL_LBS:
        return NO_TRAVEL, "45–54 mph wind with load over 30,000 lb"
    if level == HIGH and load_lbs > HEAVY_LOAD_SEVERE_LBS:
        return SEVERE, "35–44 mph wind with load over 40,000 lb"
    return level, None


@dataclass(frozen=True)
class Assessment:
    level: int
    wind_level: int
    rain_level: int
    snow_level: int
    factor: str  # which hazard decided the level: "wind" | "rain" | "snow" | "none"
    load_rule: str | None

    @property
    def name(self) -> str:
        return LEVEL_NAMES[self.level]


def assess(wind_mph: float, rain_in_hr: float, snow_in_hr: float, load_lbs: float) -> Assessment:
    """Overall level is the worst of the three hazards, after the load rules."""
    wind, load_rule = load_adjusted_wind_level(wind_mph, load_lbs)
    rain = rain_level(rain_in_hr)
    snow = snow_level(snow_in_hr)
    level = max(wind, rain, snow)
    if level == LOW:
        factor = "none"
    else:
        # Ties go to wind first: it is the only hazard affected by the load.
        factor = next(name for name, lv in (("wind", wind), ("rain", rain), ("snow", snow)) if lv == level)
    return Assessment(level, wind, rain, snow, factor, load_rule if factor == "wind" else None)


def risk_score(wind_mph: float, rain_in_hr: float, snow_in_hr: float, load_lbs: float) -> float:
    """Continuous 0–4 score for the heatmap: the integer part is always the discrete level
    from `assess`, the fraction says how far into that band the worst hazard is."""
    score = max(
        sum(_band(wind_mph, WIND_EDGES_MPH, strict_top=False)),
        sum(_band(rain_in_hr, RAIN_EDGES_IN_HR, strict_top=True)),
        sum(_band(snow_in_hr, SNOW_EDGES_IN_HR, strict_top=True)),
    )
    level = assess(wind_mph, rain_in_hr, snow_in_hr, load_lbs).level
    return float(level) if level > int(score) else score
