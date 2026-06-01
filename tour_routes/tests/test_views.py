from unittest.mock import patch

from django.urls import reverse
from rest_framework.test import APISimpleTestCase

from tour_routes.constants import (
    TOUR_ROUTE_MODE_DIRECT_FALLBACK,
    TOUR_ROUTE_MODE_TOUR,
)
from tour_routes.services.exceptions import (
    AddressResolutionError,
    PoiSearchError,
    RouteProviderError,
)
from tour_routes.types import GeoPoint, PoiCandidate, ResolvedPoint, RoutePath


class TourRouteViewTests(APISimpleTestCase):
    url = reverse("tour-route")

    def _mock_origin(self) -> ResolvedPoint:
        return ResolvedPoint(
            label="Av. Paulista, 1578 - Bela Vista, Sao Paulo",
            location=GeoPoint(lat=-23.561399, lng=-46.655881),
        )

    def _mock_destination(self) -> ResolvedPoint:
        return ResolvedPoint(
            label="Av. Paulista, 2300 - Cerqueira Cesar, Sao Paulo",
            location=GeoPoint(lat=-23.55507, lng=-46.63955),
        )

    def _mock_direct_route(self) -> RoutePath:
        return RoutePath(
            distance_m=360,
            duration_s=280,
            coordinates=[
                GeoPoint(lat=-23.561399, lng=-46.655881),
                GeoPoint(lat=-23.5591, lng=-46.6501),
                GeoPoint(lat=-23.5572, lng=-46.6448),
                GeoPoint(lat=-23.55507, lng=-46.63955),
            ],
        )

    def _mock_tour_route(self) -> RoutePath:
        return RoutePath(
            distance_m=540,
            duration_s=510,
            coordinates=[
                GeoPoint(lat=-23.561399, lng=-46.655881),
                GeoPoint(lat=-23.561414, lng=-46.655881),
                GeoPoint(lat=-23.5611, lng=-46.6530),
                GeoPoint(lat=-23.5680, lng=-46.6408),
                GeoPoint(lat=-23.55507, lng=-46.63955),
            ],
        )

    def _make_poi(
        self,
        *,
        name: str,
        category: str,
        lat: float,
        lng: float,
        progress_m: float,
        distance_from_route_m: float = 20.0,
        priority: int = 1,
    ) -> PoiCandidate:
        return PoiCandidate(
            name=name,
            category=category,
            source="overpass",
            location=GeoPoint(lat=lat, lng=lng),
            distance_from_route_m=distance_from_route_m,
            progress_m=progress_m,
            priority=priority,
        )

    def _post_route(self, *, use_addresses: bool = True):
        if use_addresses:
            return self.client.post(
                self.url,
                data={
                    "origin": {"address": "Av. Paulista, 1578, Sao Paulo"},
                    "destination": {"address": "Av. Paulista, 2300, Sao Paulo"},
                },
                format="json",
            )

        return self.client.post(
            self.url,
            data={
                "origin": {"location": {"lat": -23.561399, "lng": -46.655881}},
                "destination": {"location": {"lat": -23.55507, "lng": -46.63955}},
            },
            format="json",
        )

    @patch("tour_routes.services.poi_selector.PoiSelector.select")
    @patch("tour_routes.services.poi_search.OverpassPoiSearcher.search")
    @patch("tour_routes.services.routing.OsrmWalkingRouter.route")
    @patch("tour_routes.services.geocoding.NominatimGeocoder.resolve")
    def test_post_returns_tour_route_and_map_with_waypoint_metadata(
        self,
        mock_resolve,
        mock_route,
        mock_search,
        mock_select,
    ):
        mock_resolve.side_effect = [self._mock_origin(), self._mock_destination()]
        mock_route.return_value = self._mock_direct_route()
        mock_search.return_value = []
        mock_select.return_value = [
            self._make_poi(
                name="MASP",
                category="culture",
                lat=-23.561414,
                lng=-46.655881,
                progress_m=102.0,
                distance_from_route_m=12.0,
                priority=0,
            ),
            self._make_poi(
                name="Parque Trianon",
                category="park",
                lat=-23.5611,
                lng=-46.6530,
                progress_m=205.0,
                distance_from_route_m=30.0,
            ),
            self._make_poi(
                name="Casa das Rosas",
                category="culture",
                lat=-23.5680,
                lng=-46.6408,
                progress_m=310.0,
                distance_from_route_m=18.0,
                priority=0,
            ),
        ]

        response = self._post_route()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["route"]["mode"], TOUR_ROUTE_MODE_TOUR)
        self.assertEqual(response.data["route"]["direct_route"]["distance_m"], 360)
        self.assertGreater(
            response.data["route"]["distance_m"],
            response.data["route"]["direct_route"]["distance_m"],
        )
        self.assertGreater(response.data["route"]["duration_s"], 0)
        self.assertEqual(
            [place["name"] for place in response.data["route"]["places_to_pass"]],
            ["MASP", "Parque Trianon", "Casa das Rosas"],
        )
        self.assertEqual(
            [place["included_in_route"] for place in response.data["route"]["places_to_pass"]],
            [True, True, True],
        )
        self.assertEqual(
            [place["waypoint_order"] for place in response.data["route"]["places_to_pass"]],
            [1, 2, 3],
        )

        feature_kinds = [
            feature["properties"]["kind"] for feature in response.data["map"]["features"]
        ]
        self.assertIn("route_tour", feature_kinds)
        self.assertIn("route_direct", feature_kinds)
        self.assertIn("origin", feature_kinds)
        self.assertIn("destination", feature_kinds)
        self.assertIn("stop", feature_kinds)
        self.assertNotIn("poi", feature_kinds)

    @patch("tour_routes.services.poi_selector.PoiSelector.select")
    @patch("tour_routes.services.poi_search.OverpassPoiSearcher.search")
    @patch("tour_routes.services.routing.OsrmWalkingRouter.route")
    @patch("tour_routes.services.geocoding.NominatimGeocoder.resolve")
    def test_post_includes_all_selected_points_as_waypoints(
        self,
        mock_resolve,
        mock_route,
        mock_search,
        mock_select,
    ):
        mock_resolve.side_effect = [self._mock_origin(), self._mock_destination()]
        mock_route.return_value = self._mock_direct_route()
        mock_search.return_value = []
        mock_select.return_value = [
            self._make_poi(
                name=f"Ponto {index}",
                category="culture" if index % 3 == 0 else "park" if index % 3 == 1 else "food",
                lat=-23.5610 + (index * 0.001),
                lng=-46.6550 + (index * 0.001),
                progress_m=float(index * 100),
                priority=index % 3,
            )
            for index in range(1, 9)
        ]

        response = self._post_route()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["route"]["mode"], TOUR_ROUTE_MODE_TOUR)
        self.assertEqual(len(response.data["route"]["places_to_pass"]), 8)

        included_places = [
            place for place in response.data["route"]["places_to_pass"] if place["included_in_route"]
        ]

        self.assertEqual(len(included_places), 8)
        self.assertEqual(
            [place["waypoint_order"] for place in included_places],
            list(range(1, 9)),
        )
        self.assertEqual(
            [place["name"] for place in included_places],
            [
                "Ponto 1",
                "Ponto 2",
                "Ponto 3",
                "Ponto 4",
                "Ponto 5",
                "Ponto 6",
                "Ponto 7",
                "Ponto 8",
            ],
        )

    @patch("tour_routes.services.poi_search.OverpassPoiSearcher.search")
    @patch("tour_routes.services.routing.OsrmWalkingRouter.route")
    def test_post_returns_direct_fallback_even_without_pois(self, mock_route, mock_search):
        mock_route.return_value = self._mock_direct_route()
        mock_search.return_value = []

        response = self._post_route(use_addresses=False)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["route"]["mode"], TOUR_ROUTE_MODE_DIRECT_FALLBACK)
        self.assertEqual(response.data["route"]["places_to_pass"], [])
        self.assertEqual(
            response.data["route"]["origin"]["label"],
            "-23.561399, -46.655881",
        )
        self.assertEqual(
            response.data["route"]["distance_m"],
            response.data["route"]["direct_route"]["distance_m"],
        )
        feature_kinds = [
            feature["properties"]["kind"] for feature in response.data["map"]["features"]
        ]
        self.assertIn("route_direct", feature_kinds)
        self.assertNotIn("route_tour", feature_kinds)

    @patch("tour_routes.services.geocoding.NominatimGeocoder.resolve")
    def test_post_returns_400_when_geocoding_fails(self, mock_resolve):
        mock_resolve.side_effect = AddressResolutionError(
            "Nao foi possivel localizar o endereco 'Endereco invalido'."
        )

        response = self._post_route()

        self.assertEqual(response.status_code, 400)
        self.assertIn("Nao foi possivel localizar", response.data["detail"])

    @patch("tour_routes.services.routing.OsrmWalkingRouter.route")
    @patch("tour_routes.services.geocoding.NominatimGeocoder.resolve")
    def test_post_returns_502_when_direct_route_provider_fails(
        self,
        mock_resolve,
        mock_route,
    ):
        mock_resolve.side_effect = [self._mock_origin(), self._mock_destination()]
        mock_route.side_effect = RouteProviderError(
            "Nao foi possivel calcular a rota principal."
        )

        response = self._post_route()

        self.assertEqual(response.status_code, 502)
        self.assertEqual(
            response.data["detail"],
            "Nao foi possivel calcular a rota principal.",
        )

    @patch("tour_routes.services.poi_search.OverpassPoiSearcher.search")
    @patch("tour_routes.services.routing.OsrmWalkingRouter.route")
    def test_post_returns_route_when_poi_provider_fails(self, mock_route, mock_search):
        mock_route.return_value = self._mock_direct_route()
        mock_search.side_effect = PoiSearchError(
            "Nao foi possivel buscar pontos de interesse."
        )

        response = self._post_route(use_addresses=False)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["route"]["mode"], TOUR_ROUTE_MODE_DIRECT_FALLBACK)
        self.assertEqual(response.data["route"]["places_to_pass"], [])
