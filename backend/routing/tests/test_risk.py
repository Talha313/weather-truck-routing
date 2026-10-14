from django.test import SimpleTestCase

from routing.services import risk
from routing.services.risk import HIGH, LOW, MODERATE, NO_TRAVEL, SEVERE


class WindTableTests(SimpleTestCase):
    def test_bands_and_edges(self):
        cases = [(0, LOW), (24.9, LOW), (25, MODERATE), (34.9, MODERATE), (35, HIGH),
                 (44.9, HIGH), (45, SEVERE), (54.9, SEVERE), (55, NO_TRAVEL), (80, NO_TRAVEL)]
        for mph, level in cases:
            with self.subTest(mph=mph):
                self.assertEqual(risk.wind_level(mph), level)


class RainTableTests(SimpleTestCase):
    def test_bands_and_edges(self):
        cases = [(0, LOW), (0.099, LOW), (0.10, MODERATE), (0.25, HIGH), (0.49, HIGH),
                 (0.50, SEVERE), (1.00, SEVERE), (1.01, NO_TRAVEL)]
        for rate, level in cases:
            with self.subTest(rate=rate):
                self.assertEqual(risk.rain_level(rate), level)


class SnowTableTests(SimpleTestCase):
    def test_bands_and_edges(self):
        cases = [(0, LOW), (0.49, LOW), (0.5, MODERATE), (1.0, HIGH), (2.0, SEVERE),
                 (3.0, SEVERE), (3.01, NO_TRAVEL)]
        for rate, level in cases:
            with self.subTest(rate=rate):
                self.assertEqual(risk.snow_level(rate), level)


class LoadRuleTests(SimpleTestCase):
    def test_55_mph_is_no_travel_for_any_load(self):
        self.assertEqual(risk.assess(55, 0, 0, 0).level, NO_TRAVEL)

    def test_45_to_54_mph_heavy_load_is_no_travel(self):
        a = risk.assess(50, 0, 0, 30_001)
        self.assertEqual(a.level, NO_TRAVEL)
        self.assertIsNotNone(a.load_rule)

    def test_45_to_54_mph_at_exactly_30000_lb_stays_severe(self):
        self.assertEqual(risk.assess(50, 0, 0, 30_000).level, SEVERE)

    def test_35_to_44_mph_over_40000_lb_is_severe(self):
        self.assertEqual(risk.assess(40, 0, 0, 40_001).level, SEVERE)
        self.assertEqual(risk.assess(40, 0, 0, 40_000).level, HIGH)

    def test_load_does_not_affect_lighter_wind(self):
        self.assertEqual(risk.assess(30, 0, 0, 80_000).level, MODERATE)


class AssessTests(SimpleTestCase):
    def test_worst_hazard_wins(self):
        a = risk.assess(10, 0.3, 0.6, 20_000)
        self.assertEqual((a.level, a.factor), (HIGH, "rain"))

    def test_calm_weather_has_no_factor(self):
        self.assertEqual(risk.assess(5, 0, 0, 0).factor, "none")

    def test_load_rule_only_reported_when_wind_decides(self):
        a = risk.assess(40, 1.5, 0, 45_000)  # wind → Severe, rain → No Travel
        self.assertEqual((a.level, a.factor, a.load_rule), (NO_TRAVEL, "rain", None))


class RiskScoreTests(SimpleTestCase):
    def test_integer_part_matches_discrete_level(self):
        for wind in range(0, 70, 3):
            for rain in (0, 0.05, 0.2, 0.4, 0.8, 1.2):
                for load in (10_000, 35_000, 45_000):
                    with self.subTest(wind=wind, rain=rain, load=load):
                        score = risk.risk_score(wind, rain, 0, load)
                        self.assertEqual(int(score), risk.assess(wind, rain, 0, load).level)

    def test_score_grows_within_band(self):
        self.assertLess(risk.risk_score(26, 0, 0, 0), risk.risk_score(33, 0, 0, 0))
