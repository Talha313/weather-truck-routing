"""Converts pure driving time into elapsed clock time, optionally inserting the mandatory
FMCSA Hours-of-Service stops a property-carrying driver must take:

* a 30-minute break once 8 hours have been driven since the last break, and
* a 10-hour off-duty rest once 11 hours have been driven in a shift.

Within one shift the driver drives at most 11 h + 0.5 h break = 11.5 h on duty, which stays
inside the 14-hour window, so the window never binds. The weekly 70-hour limit is not
modelled (it needs the driver's recent history, which the app does not ask for).

A stop is only taken if driving continues afterwards: arriving after exactly 11 h of driving
needs no rest *before* arriving.
"""

import math
from dataclasses import dataclass

HOUR = 3600.0
MAX_DRIVE_PER_SHIFT = 11 * HOUR
BREAK_AFTER = 8 * HOUR
BREAK = 0.5 * HOUR
REST = 10 * HOUR


@dataclass(frozen=True)
class Stop:
    kind: str  # "break" | "rest"
    drive_s: float  # driving time at which the stop starts
    elapsed_s: float  # clock time (since departure) at which the stop starts
    duration_s: float


def elapsed_for_drive(drive_s: float, include_hos: bool) -> float:
    if not include_hos or drive_s <= 0:
        return max(drive_s, 0.0)
    shifts_done = math.ceil(drive_s / MAX_DRIVE_PER_SHIFT) - 1
    in_shift = drive_s - shifts_done * MAX_DRIVE_PER_SHIFT
    elapsed = drive_s + shifts_done * (BREAK + REST)
    if in_shift > BREAK_AFTER:
        elapsed += BREAK
    return elapsed


def stops_for_trip(total_drive_s: float, include_hos: bool) -> list[Stop]:
    if not include_hos:
        return []
    stops = []
    shift_start = 0.0
    while shift_start < total_drive_s:
        for kind, offset, duration in (
            ("break", BREAK_AFTER, BREAK),
            ("rest", MAX_DRIVE_PER_SHIFT, REST),
        ):
            at = shift_start + offset
            if at < total_drive_s:
                # `at` is the instant the driver stops; the stop itself starts after
                # the clock time of all earlier driving and stops.
                stops.append(Stop(kind, at, elapsed_for_drive(at, True), duration))
        shift_start += MAX_DRIVE_PER_SHIFT
    return stops
