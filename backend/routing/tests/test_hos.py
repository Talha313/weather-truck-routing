from django.test import SimpleTestCase

from routing.services import hos

H = 3600


class ElapsedTests(SimpleTestCase):
    def test_without_hos_elapsed_equals_driving(self):
        self.assertEqual(hos.elapsed_for_drive(20 * H, False), 20 * H)

    def test_no_break_at_exactly_8_hours(self):
        self.assertEqual(hos.elapsed_for_drive(8 * H, True), 8 * H)

    def test_break_after_8_hours(self):
        self.assertEqual(hos.elapsed_for_drive(9 * H, True), 9.5 * H)

    def test_arriving_at_11_hours_needs_no_rest(self):
        self.assertEqual(hos.elapsed_for_drive(11 * H, True), 11.5 * H)

    def test_rest_after_11_hours(self):
        # 11 h drive + 0.5 h break + 10 h rest, then 1 h more driving.
        self.assertEqual(hos.elapsed_for_drive(12 * H, True), 22.5 * H)

    def test_second_shift_break(self):
        self.assertEqual(hos.elapsed_for_drive(20 * H, True), (20 + 0.5 + 10 + 0.5) * H)


class StopsTests(SimpleTestCase):
    def test_stops_for_a_two_shift_trip(self):
        stops = hos.stops_for_trip(15 * H, True)
        self.assertEqual([(s.kind, s.drive_s / H, s.elapsed_s / H) for s in stops],
                         [("break", 8, 8), ("rest", 11, 11.5)])

    def test_short_trip_has_no_stops(self):
        self.assertEqual(hos.stops_for_trip(7 * H, True), [])
