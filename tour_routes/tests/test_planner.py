from unittest.mock import Mock

from django.test import SimpleTestCase

from tour_routes.services.planner import TourRoutePlanner
from tour_routes.types import GeoPoint, PoiCandidate, ResolvedPoint, RoutePath


class TourRoutePlannerGeometryTests(SimpleTestCase):
    def test_plan_builds_corridor_route_along_direct_route_spine(self):
        origin = ResolvedPoint(
            label="Origem",
            location=GeoPoint(lat=0.0, lng=0.0),
        )
        destination = ResolvedPoint(
            label="Destino",
            location=GeoPoint(lat=0.0, lng=0.004),
        )
        direct_route = RoutePath(
            distance_m=440,
            duration_s=320,
            coordinates=[
                GeoPoint(lat=0.0, lng=0.0),
                GeoPoint(lat=0.0, lng=0.001),
                GeoPoint(lat=0.0, lng=0.002),
                GeoPoint(lat=0.0, lng=0.003),
                GeoPoint(lat=0.0, lng=0.004),
            ],
        )

        geocoder = Mock()
        geocoder.resolve.side_effect = [origin, destination]

        router = Mock()
        router.route.return_value = direct_route

        searcher = Mock()
        searcher.search.return_value = []

        selector = Mock()
        selector.select.return_value = [
            PoiCandidate(
                name="Parada 1",
                category="culture",
                source="overpass",
                location=GeoPoint(lat=0.00045, lng=0.001),
                distance_from_route_m=50.0,
                progress_m=110.0,
                priority=0,
            ),
            PoiCandidate(
                name="Parada 2",
                category="park",
                source="overpass",
                location=GeoPoint(lat=-0.00045, lng=0.003),
                distance_from_route_m=50.0,
                progress_m=330.0,
                priority=1,
            ),
        ]

        planner = TourRoutePlanner(
            geocoder=geocoder,
            router=router,
            poi_searcher=searcher,
            poi_selector=selector,
        )

        result, _ = planner.plan(
            origin_input={"address": "origem"},
            destination_input={"address": "destino"},
        )

        self.assertEqual(result.mode, "tour")
        self.assertEqual([place.waypoint_order for place in result.places_to_pass], [1, 2])
        self.assertIn(GeoPoint(lat=0.0, lng=0.001), result.route_path.coordinates)
        self.assertIn(GeoPoint(lat=0.0, lng=0.003), result.route_path.coordinates)
        self.assertGreater(len(result.route_path.coordinates), 6)
        self.assertLess(result.route_path.distance_m, 1200)
