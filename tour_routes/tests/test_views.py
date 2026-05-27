from unittest.mock import patch

from django.urls import reverse
from rest_framework.test import APISimpleTestCase

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

    def _mock_route(self) -> RoutePath:
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

    @patch("tour_routes.services.poi_search.OverpassPoiSearcher.search")
    @patch("tour_routes.services.routing.OsrmWalkingRouter.route")
    @patch("tour_routes.services.geocoding.NominatimGeocoder.resolve")
    def test_post_returns_route_and_map_with_sorted_places(
        self,
        mock_resolve,
        mock_route,
        mock_search,
    ):
        mock_resolve.side_effect = [self._mock_origin(), self._mock_destination()]
        mock_route.return_value = self._mock_route()
        mock_search.return_value = [
            PoiCandidate(
                name="Cafe na Paulista",
                category="food",
                source="overpass",
                location=GeoPoint(lat=-23.5587, lng=-46.6494),
                distance_from_route_m=28.0,
                progress_m=108.0,
                priority=2,
            ),
            PoiCandidate(
                name="MASP",
                category="culture",
                source="overpass",
                location=GeoPoint(lat=-23.561414, lng=-46.655881),
                distance_from_route_m=12.0,
                progress_m=102.0,
                priority=0,
            ),
            PoiCandidate(
                name="Parque Trianon",
                category="park",
                source="overpass",
                location=GeoPoint(lat=-23.5611, lng=-46.6530),
                distance_from_route_m=30.0,
                progress_m=205.0,
                priority=1,
            ),
            PoiCandidate(
                name="Casa das Rosas",
                category="culture",
                source="overpass",
                location=GeoPoint(lat=-23.5680, lng=-46.6408),
                distance_from_route_m=18.0,
                progress_m=310.0,
                priority=0,
            ),
        ]

        response = self.client.post(
            self.url,
            data={
                "origin": {"address": "Av. Paulista, 1578, Sao Paulo"},
                "destination": {"address": "Av. Paulista, 2300, Sao Paulo"},
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["route"]["distance_m"], 360)
        self.assertEqual(
            [place["name"] for place in response.data["route"]["places_to_pass"]],
            ["MASP", "Parque Trianon", "Casa das Rosas"],
        )
        self.assertEqual(response.data["map"]["type"], "FeatureCollection")
        self.assertEqual(response.data["map"]["features"][0]["geometry"]["type"], "LineString")

    @patch("tour_routes.services.poi_search.OverpassPoiSearcher.search")
    @patch("tour_routes.services.routing.OsrmWalkingRouter.route")
    def test_post_returns_route_even_without_pois(self, mock_route, mock_search):
        mock_route.return_value = self._mock_route()
        mock_search.return_value = []

        response = self.client.post(
            self.url,
            data={
                "origin": {"location": {"lat": -23.561399, "lng": -46.655881}},
                "destination": {"location": {"lat": -23.55507, "lng": -46.63955}},
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["route"]["places_to_pass"], [])
        self.assertEqual(
            response.data["route"]["origin"]["label"],
            "-23.561399, -46.655881",
        )

    @patch("tour_routes.services.geocoding.NominatimGeocoder.resolve")
    def test_post_returns_400_when_geocoding_fails(self, mock_resolve):
        mock_resolve.side_effect = AddressResolutionError(
            "Nao foi possivel localizar o endereco 'Endereco invalido'."
        )

        response = self.client.post(
            self.url,
            data={
                "origin": {"address": "Endereco invalido"},
                "destination": {"address": "Av. Paulista, 2300, Sao Paulo"},
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Nao foi possivel localizar", response.data["detail"])

    @patch("tour_routes.services.routing.OsrmWalkingRouter.route")
    @patch("tour_routes.services.geocoding.NominatimGeocoder.resolve")
    def test_post_returns_502_when_route_provider_fails(
        self,
        mock_resolve,
        mock_route,
    ):
        mock_resolve.side_effect = [self._mock_origin(), self._mock_destination()]
        mock_route.side_effect = RouteProviderError(
            "Nao foi possivel calcular a rota principal."
        )

        response = self.client.post(
            self.url,
            data={
                "origin": {"address": "Av. Paulista, 1578, Sao Paulo"},
                "destination": {"address": "Av. Paulista, 2300, Sao Paulo"},
            },
            format="json",
        )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(
            response.data["detail"],
            "Nao foi possivel calcular a rota principal.",
        )

    @patch("tour_routes.services.poi_search.OverpassPoiSearcher.search")
    @patch("tour_routes.services.routing.OsrmWalkingRouter.route")
    def test_post_returns_route_when_poi_provider_fails(self, mock_route, mock_search):
        mock_route.return_value = self._mock_route()
        mock_search.side_effect = PoiSearchError(
            "Nao foi possivel buscar pontos de interesse."
        )

        response = self.client.post(
            self.url,
            data={
                "origin": {"location": {"lat": -23.561399, "lng": -46.655881}},
                "destination": {"location": {"lat": -23.55507, "lng": -46.63955}},
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["route"]["places_to_pass"], [])
