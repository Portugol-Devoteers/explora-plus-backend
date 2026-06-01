from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

from tour_routes.constants import (
    TOUR_ROUTE_MODE_DIRECT_FALLBACK,
    TOUR_ROUTE_MODE_TOUR,
)
from tour_routes.models import SavedTourRoute, TourRouteCache
from tour_routes.persistence import build_search_cache_key
from tour_routes.serializers import serialize_result
from tour_routes.services.exceptions import TourRouteError
from tour_routes.services.map_builder import GeoJsonMapBuilder
from tour_routes.types import GeoPoint, ResolvedPoint, RoutePath, RoutePoi, TourRouteResult

User = get_user_model()


class TourRouteViewTests(APITestCase):
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

    def _make_route_poi(
        self,
        *,
        stop_id: str,
        name: str,
        category: str,
        lat: float,
        lng: float,
        included_in_route: bool = True,
        waypoint_order: int | None = None,
        distance_from_route_m: float = 20.0,
    ) -> RoutePoi:
        return RoutePoi(
            stop_id=stop_id,
            name=name,
            category=category,
            source="overpass",
            location=GeoPoint(lat=lat, lng=lng),
            distance_from_route_m=distance_from_route_m,
            progress_m=0.0,
            priority=0,
            included_in_route=included_in_route,
            waypoint_order=waypoint_order,
        )

    def _build_result(
        self,
        *,
        places_to_pass: list[RoutePoi],
        mode: str = TOUR_ROUTE_MODE_TOUR,
        route_path: RoutePath | None = None,
        direct_route_path: RoutePath | None = None,
        tour_route_path: RoutePath | None = None,
    ) -> TourRouteResult:
        origin = self._mock_origin()
        destination = self._mock_destination()
        direct = direct_route_path or self._mock_direct_route()
        active_route = route_path or (tour_route_path or self._mock_tour_route())
        final_tour_route = (
            tour_route_path
            if tour_route_path is not None
            else active_route
            if mode == TOUR_ROUTE_MODE_TOUR
            else None
        )
        return TourRouteResult(
            origin=origin,
            destination=destination,
            route_path=active_route,
            direct_route_path=direct,
            tour_route_path=final_tour_route,
            mode=mode,
            places_to_pass=places_to_pass,
        )

    def _build_payload(self, result: TourRouteResult, *, saved_route_id: int | None = None):
        map_payload = GeoJsonMapBuilder().build(result)
        return serialize_result(result, map_payload, saved_route_id=saved_route_id)

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

    def _post_route_with_invalid_token(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer definitely-invalid-token")
        try:
            return self._post_route()
        finally:
            self.client.credentials()

    @patch("tour_routes.views.build_default_planner")
    def test_post_returns_tour_route_and_map_with_waypoint_metadata(self, mock_build_planner):
        result = self._build_result(
            places_to_pass=[
                self._make_route_poi(
                    stop_id="masp-stop",
                    name="MASP",
                    category="culture",
                    lat=-23.561414,
                    lng=-46.655881,
                    waypoint_order=1,
                    distance_from_route_m=12.0,
                ),
                self._make_route_poi(
                    stop_id="trianon-stop",
                    name="Parque Trianon",
                    category="park",
                    lat=-23.5611,
                    lng=-46.6530,
                    waypoint_order=2,
                    distance_from_route_m=30.0,
                ),
                self._make_route_poi(
                    stop_id="rosas-stop",
                    name="Casa das Rosas",
                    category="culture",
                    lat=-23.5680,
                    lng=-46.6408,
                    waypoint_order=3,
                    distance_from_route_m=18.0,
                ),
            ],
        )
        planner = Mock()
        planner.plan.return_value = (result, GeoJsonMapBuilder().build(result))
        mock_build_planner.return_value = planner

        response = self._post_route()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["route"]["mode"], TOUR_ROUTE_MODE_TOUR)
        self.assertEqual(response.data["route"]["saved_route_id"], None)
        self.assertEqual(response.data["route"]["direct_route"]["distance_m"], 360)
        self.assertGreater(
            response.data["route"]["distance_m"],
            response.data["route"]["direct_route"]["distance_m"],
        )
        self.assertEqual(
            [place["stop_id"] for place in response.data["route"]["places_to_pass"]],
            ["masp-stop", "trianon-stop", "rosas-stop"],
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
        self.assertIn("stop", feature_kinds)

    @patch("tour_routes.views.build_default_planner")
    def test_post_includes_all_selected_points_as_waypoints(self, mock_build_planner):
        places = [
            self._make_route_poi(
                stop_id=f"stop-{index}",
                name=f"Ponto {index}",
                category="culture" if index % 3 == 0 else "park" if index % 3 == 1 else "food",
                lat=-23.5610 + (index * 0.001),
                lng=-46.6550 + (index * 0.001),
                waypoint_order=index,
            )
            for index in range(1, 9)
        ]
        result = self._build_result(places_to_pass=places)
        planner = Mock()
        planner.plan.return_value = (result, GeoJsonMapBuilder().build(result))
        mock_build_planner.return_value = planner

        response = self._post_route()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["route"]["places_to_pass"]), 8)
        self.assertEqual(
            [place["waypoint_order"] for place in response.data["route"]["places_to_pass"]],
            list(range(1, 9)),
        )

    @patch("tour_routes.views.build_default_planner")
    def test_post_returns_direct_fallback_even_without_pois(self, mock_build_planner):
        result = self._build_result(
            places_to_pass=[],
            mode=TOUR_ROUTE_MODE_DIRECT_FALLBACK,
            route_path=self._mock_direct_route(),
            direct_route_path=self._mock_direct_route(),
            tour_route_path=None,
        )
        planner = Mock()
        planner.plan.return_value = (result, GeoJsonMapBuilder().build(result))
        mock_build_planner.return_value = planner

        response = self._post_route(use_addresses=False)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["route"]["mode"], TOUR_ROUTE_MODE_DIRECT_FALLBACK)
        self.assertEqual(response.data["route"]["places_to_pass"], [])
        self.assertEqual(
            response.data["route"]["origin"]["label"],
            "Av. Paulista, 1578 - Bela Vista, Sao Paulo",
        )
        self.assertEqual(
            response.data["route"]["distance_m"],
            response.data["route"]["direct_route"]["distance_m"],
        )

    @patch("tour_routes.views.build_default_planner")
    def test_post_returns_tour_route_error_status(self, mock_build_planner):
        planner = Mock()
        planner.plan.side_effect = TourRouteError("Falhou")
        planner.plan.side_effect.status_code = 502
        mock_build_planner.return_value = planner

        response = self._post_route()

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.data["detail"], "Falhou")

    @patch("tour_routes.views.build_default_planner")
    def test_post_ignores_invalid_token_for_public_route(self, mock_build_planner):
        result = self._build_result(
            places_to_pass=[
                self._make_route_poi(
                    stop_id="masp-stop",
                    name="MASP",
                    category="culture",
                    lat=-23.561414,
                    lng=-46.655881,
                    waypoint_order=1,
                )
            ]
        )
        planner = Mock()
        planner.plan.return_value = (result, GeoJsonMapBuilder().build(result))
        mock_build_planner.return_value = planner

        response = self._post_route_with_invalid_token()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["route"]["saved_route_id"], None)
        self.assertEqual(TourRouteCache.objects.count(), 1)

    @patch("tour_routes.views.build_default_planner")
    def test_post_uses_cache_before_planner(self, mock_build_planner):
        cached_result = self._build_result(
            places_to_pass=[
                self._make_route_poi(
                    stop_id="cached-stop",
                    name="MASP",
                    category="culture",
                    lat=-23.561414,
                    lng=-46.655881,
                    waypoint_order=1,
                )
            ]
        )
        cached_payload = self._build_payload(cached_result)
        cache_key, canonical_payload = build_search_cache_key(
            origin_input={"address": "Av. Paulista, 1578, Sao Paulo"},
            destination_input={"address": "Av. Paulista, 2300, Sao Paulo"},
        )
        cache = TourRouteCache.objects.create(
            cache_key=cache_key,
            origin_query="Av. Paulista, 1578, Sao Paulo",
            destination_query="Av. Paulista, 2300, Sao Paulo",
            search_payload=canonical_payload,
            route_payload=cached_payload["route"],
            map_payload=cached_payload["map"],
            hit_count=1,
        )

        response = self._post_route()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["route"]["places_to_pass"][0]["stop_id"], "cached-stop")
        self.assertEqual(response.data["route"]["saved_route_id"], None)
        cache.refresh_from_db()
        self.assertEqual(cache.hit_count, 2)
        mock_build_planner.assert_not_called()

    @patch("tour_routes.views.build_default_planner")
    def test_post_recomputes_when_cached_route_has_no_pois(self, mock_build_planner):
        fallback_result = self._build_result(
            places_to_pass=[],
            mode=TOUR_ROUTE_MODE_DIRECT_FALLBACK,
            route_path=self._mock_direct_route(),
            direct_route_path=self._mock_direct_route(),
            tour_route_path=None,
        )
        fallback_payload = self._build_payload(fallback_result)
        cache_key, canonical_payload = build_search_cache_key(
            origin_input={"address": "Av. Paulista, 1578, Sao Paulo"},
            destination_input={"address": "Av. Paulista, 2300, Sao Paulo"},
        )
        cache = TourRouteCache.objects.create(
            cache_key=cache_key,
            origin_query="Av. Paulista, 1578, Sao Paulo",
            destination_query="Av. Paulista, 2300, Sao Paulo",
            search_payload=canonical_payload,
            route_payload=fallback_payload["route"],
            map_payload=fallback_payload["map"],
            hit_count=1,
        )

        refreshed_result = self._build_result(
            places_to_pass=[
                self._make_route_poi(
                    stop_id="masp-stop",
                    name="MASP",
                    category="culture",
                    lat=-23.561414,
                    lng=-46.655881,
                    waypoint_order=1,
                )
            ]
        )
        planner = Mock()
        planner.plan.return_value = (refreshed_result, GeoJsonMapBuilder().build(refreshed_result))
        mock_build_planner.return_value = planner

        response = self._post_route()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["route"]["mode"], TOUR_ROUTE_MODE_TOUR)
        self.assertEqual(len(response.data["route"]["places_to_pass"]), 1)
        cache.refresh_from_db()
        self.assertEqual(cache.route_payload["mode"], TOUR_ROUTE_MODE_TOUR)
        self.assertEqual(len(cache.route_payload["places_to_pass"]), 1)
        self.assertEqual(cache.hit_count, 2)
        mock_build_planner.assert_called_once()

    @patch("tour_routes.views.build_default_planner")
    def test_post_creates_saved_route_for_authenticated_user(self, mock_build_planner):
        user = User.objects.create_user(
            username="route-user",
            email="route@example.com",
            password="secret123",
        )
        self.client.force_authenticate(user=user)

        result = self._build_result(
            places_to_pass=[
                self._make_route_poi(
                    stop_id="masp-stop",
                    name="MASP",
                    category="culture",
                    lat=-23.561414,
                    lng=-46.655881,
                    waypoint_order=1,
                )
            ]
        )
        planner = Mock()
        planner.plan.return_value = (result, GeoJsonMapBuilder().build(result))
        mock_build_planner.return_value = planner

        response = self._post_route()

        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.data["route"]["saved_route_id"])
        self.assertEqual(SavedTourRoute.objects.count(), 1)
        saved_route = SavedTourRoute.objects.get()
        self.assertEqual(saved_route.user, user)
        self.assertEqual(saved_route.route_payload["saved_route_id"], saved_route.id)
        self.assertEqual(TourRouteCache.objects.count(), 1)

    @patch("tour_routes.views.build_default_planner")
    def test_delete_stop_updates_saved_route_snapshot(self, mock_build_planner):
        user = User.objects.create_user(
            username="saved-user",
            email="saved@example.com",
            password="secret123",
        )
        self.client.force_authenticate(user=user)

        base_result = self._build_result(
            places_to_pass=[
                self._make_route_poi(
                    stop_id="stop-a",
                    name="MASP",
                    category="culture",
                    lat=-23.561414,
                    lng=-46.655881,
                    waypoint_order=1,
                ),
                self._make_route_poi(
                    stop_id="stop-b",
                    name="Parque Trianon",
                    category="park",
                    lat=-23.5611,
                    lng=-46.6530,
                    waypoint_order=2,
                ),
            ]
        )
        base_payload = self._build_payload(base_result)
        cache = TourRouteCache.objects.create(
            cache_key="cache-stop-delete",
            origin_query="Av. Paulista, 1578, Sao Paulo",
            destination_query="Av. Paulista, 2300, Sao Paulo",
            search_payload={},
            route_payload=base_payload["route"],
            map_payload=base_payload["map"],
            hit_count=1,
        )
        saved_route = SavedTourRoute.objects.create(
            user=user,
            cache=cache,
            origin_query=cache.origin_query,
            destination_query=cache.destination_query,
            origin_label=base_payload["route"]["origin"]["label"],
            destination_label=base_payload["route"]["destination"]["label"],
            distance_m=base_payload["route"]["distance_m"],
            duration_s=base_payload["route"]["duration_s"],
            route_payload={**base_payload["route"], "saved_route_id": 99},
            map_payload=base_payload["map"],
        )

        rebuilt_result = self._build_result(
            places_to_pass=[
                self._make_route_poi(
                    stop_id="stop-b",
                    name="Parque Trianon",
                    category="park",
                    lat=-23.5611,
                    lng=-46.6530,
                    waypoint_order=1,
                )
            ]
        )
        planner = Mock()
        planner.rebuild_from_payload.return_value = (
            rebuilt_result,
            GeoJsonMapBuilder().build(rebuilt_result),
        )
        mock_build_planner.return_value = planner

        response = self.client.delete(
            reverse(
                "saved-tour-route-stop-delete",
                kwargs={"route_id": saved_route.id, "stop_id": "stop-a"},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["route"]["saved_route_id"], saved_route.id)
        self.assertEqual(
            [place["stop_id"] for place in response.data["route"]["places_to_pass"]],
            ["stop-b"],
        )
        saved_route.refresh_from_db()
        self.assertEqual(saved_route.excluded_stop_ids, ["stop-a"])
        self.assertEqual(saved_route.route_payload["saved_route_id"], saved_route.id)
