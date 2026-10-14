"""Route recommendation: a strict lexicographic ranking, per the assessment.

    1. fewest Severe miles  2. fewest High miles  3. lowest average risk  4. shortest travel time

No Travel is worse than Severe but is not in the spec's list, so it is ranked first: a route
that crosses No Travel conditions only wins when every route does. Miles are compared at
0.1 mile and average risk at 0.01 so that floating-point noise never decides a ranking.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class RouteScore:
    no_travel_miles: float
    severe_miles: float
    high_miles: float
    avg_risk: float
    travel_s: float

    def key(self) -> tuple:
        return (
            round(self.no_travel_miles, 1),
            round(self.severe_miles, 1),
            round(self.high_miles, 1),
            round(self.avg_risk, 2),
            self.travel_s,
        )


CRITERIA = (
    ("no_travel_miles", "No Travel miles"),
    ("severe_miles", "Severe miles"),
    ("high_miles", "High miles"),
    ("avg_risk", "average risk"),
    ("travel_s", "travel time"),
)


def rank(scores: list[RouteScore]) -> list[int]:
    """Indices of `scores`, best first. Stable, so equal routes keep their engine order."""
    return sorted(range(len(scores)), key=lambda i: scores[i].key())


def deciding_criterion(winner: RouteScore, other: RouteScore) -> tuple[str, str] | None:
    """The first criterion on which `winner` beats `other`, as (field, label)."""
    for (field, label), a, b in zip(CRITERIA, winner.key(), other.key()):
        if a != b:
            return (field, label) if a < b else None
    return None


def explain(winner: RouteScore, winner_name: str, other: RouteScore, other_name: str) -> str:
    decided = deciding_criterion(winner, other)
    if decided is None:
        return f"{winner_name} and {other_name} are equivalent on every criterion."
    field, label = decided
    a, b = getattr(winner, field), getattr(other, field)
    if field == "travel_s":
        diff_min = round((b - a) / 60)
        return f"Same weather exposure as {other_name}, but {_minutes(diff_min)} faster."
    if field == "avg_risk":
        return f"Lower average risk than {other_name} ({a:.2f} vs {b:.2f})."
    return f"{_mi(b - a)} fewer {label} than {other_name} ({_mi(a)} vs {_mi(b)} mi)."


def _mi(value: float) -> str:
    return f"{value:.1f}" if value < 10 else f"{value:.0f}"


def _minutes(total: int) -> str:
    h, m = divmod(abs(total), 60)
    return f"{h} h {m} min" if h else f"{m} min"
