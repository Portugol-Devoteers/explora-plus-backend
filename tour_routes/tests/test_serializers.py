from django.test import SimpleTestCase

from tour_routes.serializers import (
    SavedTourRouteStopStateSerializer,
    TourRouteRequestSerializer,
)


class TourRouteRequestSerializerTests(SimpleTestCase):
    def test_accepts_address_input(self):
        serializer = TourRouteRequestSerializer(
            data={
                "origin": {"address": "Av. Paulista, 1578, Sao Paulo"},
                "destination": {"address": "Av. Paulista, 2300, Sao Paulo"},
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_accepts_coordinate_input(self):
        serializer = TourRouteRequestSerializer(
            data={
                "origin": {"location": {"lat": -23.561399, "lng": -46.655881}},
                "destination": {"location": {"lat": -23.55507, "lng": -46.63955}},
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_rejects_address_and_location_together(self):
        serializer = TourRouteRequestSerializer(
            data={
                "origin": {
                    "address": "Av. Paulista, 1578, Sao Paulo",
                    "location": {"lat": -23.561399, "lng": -46.655881},
                },
                "destination": {"address": "Av. Paulista, 2300, Sao Paulo"},
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("origin", serializer.errors)

    def test_rejects_endpoint_without_address_or_location(self):
        serializer = TourRouteRequestSerializer(
            data={
                "origin": {},
                "destination": {"address": "Av. Paulista, 2300, Sao Paulo"},
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("origin", serializer.errors)

    def test_accepts_stop_state_patch_payload(self):
        serializer = SavedTourRouteStopStateSerializer(data={"state": "visited"})

        self.assertTrue(serializer.is_valid(), serializer.errors)
