from datetime import datetime, timezone

from django.test import SimpleTestCase

from routing.services import planner, weather
from routing.services.routing import Route


def straight_route(miles=100.0, mph=50.0):
    # Due north along a meridian: 1° latitude ≈ 69.09 miles.
    n = 101
    coords = [(40 + (miles / 69.09) * i / (n - 1), -90.0) for i in range(n)]
    from routing.services import geo
    cum = geo.cumulative_miles(coords)
    return Route(coords, cum, [m / mph * 3600 for m in cum], "Test Rd", "test")


class CheckpointTests(SimpleTestCase):
    def test_spacing_and_endpoints(self):
        route = straight_route(100)
        cps = planner.sample_checkpoints(route, 25, include_hos=False)
        self.assertEqual([round(c.mile) for c in cps], [0, 25, 50, 75, 100])

    def test_partial_last_interval_gets_a_destination_checkpoint(self):
        route = straight_route(60)
        cps = planner.sample_checkpoints(route, 25, include_hos=False)
        self.assertEqual([round(c.mile) for c in cps], [0, 25, 50, 60])

    def test_coverage_partitions_the_route(self):
        route = straight_route(60)
        cps = planner.sample_checkpoints(route, 10, include_hos=False)
        self.assertAlmostEqual(sum(c.covers[1] - c.covers[0] for c in cps), route.distance_miles, places=6)
        for a, b in zip(cps, cps[1:]):
            self.assertAlmostEqual(a.covers[1], b.covers[0])

    def test_eta_follows_driving_time(self):
        cps = planner.sample_checkpoints(straight_route(100, mph=50), 50, include_hos=False)
        self.assertAlmostEqual(cps[1].elapsed_s, 3600, delta=5)


class WeatherSeriesTests(SimpleTestCase):
    def setUp(self):
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.series = weather.Series(
            start=start,
            wind=[10, 20, 30],
            gust=[15, 25, 35],
            rain=[0.0, 0.2, 0.6],
            snow=[0, 0, 0],
            temp=[30, 31, 32],
            code=[0, 61, 63],
        )
        self.start = start

    def test_wind_interpolates_and_precip_uses_hour_ending_after(self):
        c = self.series.at(self.start.replace(minute=30))
        self.assertAlmostEqual(c.wind_mph, 15)
        self.assertEqual(c.rain_in_hr, 0.2)  # rain during 00:00–01:00 is stamped 01:00

    def test_outside_forecast_is_none(self):
        self.assertIsNone(self.series.at(self.start.replace(hour=5)))

    def test_frame_uses_precip_of_following_hour(self):
        self.assertEqual(self.series.frame(1).rain_in_hr, 0.6)
