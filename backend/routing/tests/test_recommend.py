from django.test import SimpleTestCase

from routing.services.recommend import RouteScore, explain, rank


def score(nt=0, sev=0, high=0, avg=0.0, hours=10):
    return RouteScore(nt, sev, high, avg, hours * 3600)


class RankTests(SimpleTestCase):
    def test_fewest_severe_miles_beats_faster_route(self):
        self.assertEqual(rank([score(sev=10, hours=8), score(sev=0, hours=12)]), [1, 0])

    def test_high_miles_break_severe_tie(self):
        self.assertEqual(rank([score(sev=5, high=30), score(sev=5, high=10)]), [1, 0])

    def test_average_risk_breaks_high_tie(self):
        self.assertEqual(rank([score(high=10, avg=0.5), score(high=10, avg=0.2)]), [1, 0])

    def test_travel_time_is_last(self):
        self.assertEqual(rank([score(hours=11), score(hours=10), score(hours=12)]), [1, 0, 2])

    def test_no_travel_miles_rank_before_severe(self):
        self.assertEqual(rank([score(nt=5, sev=0), score(nt=0, sev=200)]), [1, 0])

    def test_float_noise_does_not_decide(self):
        self.assertEqual(rank([score(sev=10.0000001, hours=9), score(sev=10.0, hours=10)]), [0, 1])


class ExplainTests(SimpleTestCase):
    def test_mentions_deciding_criterion(self):
        text = explain(score(sev=0), "Route A", score(sev=25), "Route B")
        self.assertIn("fewer Severe miles", text)

    def test_time_explanation(self):
        text = explain(score(hours=10), "Route A", score(hours=11), "Route B")
        self.assertIn("1 h 0 min faster", text)
