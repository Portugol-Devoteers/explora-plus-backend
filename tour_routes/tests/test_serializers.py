from django.test import SimpleTestCase

from tour_routes.serializers import (
    SavedTourRouteStopStateSerializer,
    TourRoutePreferencesSerializer,
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


class TourRoutePreferencesSerializerTests(SimpleTestCase):
    def test_accepts_valid_preferences_payload(self):
        serializer = TourRoutePreferencesSerializer(
            data={
                "include_culture": True,
                "include_park": False,
                "include_food": True,
                "poi_spacing_m": 75,
                "max_search_radius_m": 400,
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_rejects_payload_with_all_categories_disabled(self):
        serializer = TourRoutePreferencesSerializer(
            data={
                "include_culture": False,
                "include_park": False,
                "include_food": False,
                "poi_spacing_m": 100,
                "max_search_radius_m": 250,
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("non_field_errors", serializer.errors)

    def test_rejects_payload_with_invalid_spacing_preset(self):
        serializer = TourRoutePreferencesSerializer(
            data={
                "include_culture": True,
                "include_park": True,
                "include_food": True,
                "poi_spacing_m": 120,
                "max_search_radius_m": 250,
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("poi_spacing_m", serializer.errors)

    def test_rejects_payload_with_invalid_radius_preset(self):
        serializer = TourRoutePreferencesSerializer(
            data={
                "include_culture": True,
                "include_park": True,
                "include_food": True,
                "poi_spacing_m": 100,
                "max_search_radius_m": 300,
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("max_search_radius_m", serializer.errors)
