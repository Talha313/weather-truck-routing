from django.test import SimpleTestCase

from routing.services import geo


class GeoTests(SimpleTestCase):
    def test_decode_polyline6(self):
        # Valhalla's documented example encodes these two points at precision 6.
        encoded = geo.decode_polyline("_izlhA~rlgdF_{geC~ywl@", 6)
        self.assertAlmostEqual(encoded[0][0], 38.5, places=5)
        self.assertAlmostEqual(encoded[0][1], -120.2, places=5)
        self.assertAlmostEqual(encoded[1][0], 40.7, places=5)

    def test_haversine_one_degree_latitude(self):
        self.assertAlmostEqual(geo.haversine_mi((0, 0), (1, 0)), 69.09, delta=0.05)

    def test_simplify_keeps_endpoints_and_corners(self):
        line = [(0, 0), (0, 0.5), (0, 1), (1, 1)]
        self.assertEqual(geo.simplify_indices(line, 0.01), [0, 2, 3])
