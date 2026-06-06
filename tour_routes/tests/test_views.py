from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.utils import timezone
from django.urls import reverse
from rest_framework.test import APITestCase

from core.domain import ROUTE_STOP_STATE_EXCLUDED
from places.models import Place, UserPlaceState
from tour_routes.constants import (
    TOUR_ROUTE_DEFAULT_MAX_SEARCH_RADIUS_M,
    TOUR_ROUTE_DEFAULT_POI_SPACING_M,
    TOUR_ROUTE_MODE_DIRECT_FALLBACK,
    TOUR_ROUTE_MODE_TOUR,
    TOUR_ROUTE_STOP_STATE_ACTIVE,
    TOUR_ROUTE_STOP_STATE_VISITED,
)
from tour_routes.models import (
    RouteSearchCache,
    TourRoute,
    TourRouteStop,
    UserRouteSearchPreference,
)
from tour_routes.persistence import build_search_cache_key, create_tour_route
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
        state: str = TOUR_ROUTE_STOP_STATE_ACTIVE,
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
            state=state,
            osm_type="way",
            osm_id=123,
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

    def _post_route(self):
        return self.client.post(
            self.url,
            data={
                "origin": {"address": "Av. Paulista, 1578, Sao Paulo"},
                "destination": {"address": "Av. Paulista, 2300, Sao Paulo"},
            },
            format="json",
        )

    def _create_cached_route(self, *, user, base_result: TourRouteResult, current_result: TourRouteResult | None = None):
        base_payload = self._build_payload(base_result)
        cache = RouteSearchCache.objects.create(
            cache_key=f"cache-{RouteSearchCache.objects.count()+1}",
            origin_query="Av. Paulista, 1578, Sao Paulo",
            destination_query="Av. Paulista, 2300, Sao Paulo",
            search_payload={},
            route_payload=base_payload["route"],
            map_payload=base_payload["map"],
            hit_count=1,
        )
        current_payload = self._build_payload(current_result or base_result)
        route = create_tour_route(
            user=user,
            search_cache=cache,
            origin_query=cache.origin_query,
            destination_query=cache.destination_query,
            base_route_payload=base_payload["route"],
            current_route_payload=current_payload["route"],
            visited_stop_ids=[
                place.stop_id
                for place in (current_result or base_result).places_to_pass
                if place.state == TOUR_ROUTE_STOP_STATE_VISITED
            ],
        )
        return route

    @patch("tour_routes.views.build_default_planner")
    def test_post_public_route_creates_cache_and_canonical_places(self, mock_build_planner):
        result = self._build_result(
            places_to_pass=[
                self._make_route_poi(
                    stop_id="masp-stop",
                    name="MASP",
                    category="culture",
                    lat=-23.561414,
                    lng=-46.655881,
                    waypoint_order=1,
                ),
                self._make_route_poi(
                    stop_id="trianon-stop",
                    name="Parque Trianon",
                    category="park",
                    lat=-23.5611,
                    lng=-46.6530,
                    waypoint_order=2,
                ),
            ]
        )
        planner = Mock()
        planner.plan.return_value = (result, GeoJsonMapBuilder().build(result))
        mock_build_planner.return_value = planner

        response = self._post_route()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(RouteSearchCache.objects.count(), 1)
        self.assertEqual(Place.objects.count(), 2)
        self.assertEqual(response.data["route"]["saved_route_id"], None)
        self.assertEqual(
            [place["stop_id"] for place in response.data["route"]["places_to_pass"]],
            ["masp-stop", "trianon-stop"],
        )

    @patch("tour_routes.views.build_default_planner")
    def test_authenticated_post_creates_relational_route_and_user_place_states(self, mock_build_planner):
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
        route = TourRoute.objects.get(user=user)
        self.assertEqual(response.data["route"]["saved_route_id"], route.id)
        self.assertEqual(route.stops.count(), 1)
        self.assertEqual(UserPlaceState.objects.filter(user=user).count(), 1)
        self.assertEqual(route.stops.get().place.source_ref, "masp-stop")

    @patch("tour_routes.views.build_default_planner")
    def test_authenticated_post_applies_global_visited_places(self, mock_build_planner):
        user = User.objects.create_user(
            username="visited-user",
            email="visited@example.com",
            password="secret123",
        )
        self.client.force_authenticate(user=user)
        place = Place.objects.create(
            slug="masp-existing",
            category_id=self._ensure_category("culture").id,
            name="MASP",
            summary="Museu",
            source="overpass",
            source_ref="masp-stop",
            location=Point(-46.655881, -23.561414, srid=4326),
        )
        UserPlaceState.objects.create(user=user, place=place, is_visited=True, visited_at=timezone.now())

        initial_result = self._build_result(
            places_to_pass=[
                self._make_route_poi(
                    stop_id="masp-stop",
                    name="MASP",
                    category="culture",
                    lat=-23.561414,
                    lng=-46.655881,
                    waypoint_order=1,
                ),
                self._make_route_poi(
                    stop_id="trianon-stop",
                    name="Parque Trianon",
                    category="park",
                    lat=-23.5611,
                    lng=-46.6530,
                    waypoint_order=2,
                ),
            ]
        )
        rebuilt_result = self._build_result(
            places_to_pass=[
                self._make_route_poi(
                    stop_id="masp-stop",
                    name="MASP",
                    category="culture",
                    lat=-23.561414,
                    lng=-46.655881,
                    included_in_route=False,
                    waypoint_order=None,
                    state=TOUR_ROUTE_STOP_STATE_VISITED,
                ),
                self._make_route_poi(
                    stop_id="trianon-stop",
                    name="Parque Trianon",
                    category="park",
                    lat=-23.5611,
                    lng=-46.6530,
                    waypoint_order=1,
                ),
            ]
        )
        planner = Mock()
        planner.plan.return_value = (initial_result, GeoJsonMapBuilder().build(initial_result))
        planner.rebuild_from_payload.return_value = (
            rebuilt_result,
            GeoJsonMapBuilder().build(rebuilt_result),
        )
        mock_build_planner.return_value = planner

        response = self._post_route()

        self.assertEqual(response.status_code, 200)
        route = TourRoute.objects.get(user=user)
        stop = route.stops.select_related("place").get(place__source_ref="masp-stop")
        self.assertEqual(stop.state, TOUR_ROUTE_STOP_STATE_VISITED)
        self.assertFalse(response.data["route"]["places_to_pass"][0]["included_in_route"])

    @patch("tour_routes.views.build_default_planner")
    def test_delete_stop_marks_route_stop_as_excluded_and_keeps_library(self, mock_build_planner):
        user = User.objects.create_user(
            username="delete-user",
            email="delete@example.com",
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
        route = self._create_cached_route(user=user, base_result=base_result)
        ensure_place_states = UserPlaceState.objects.filter(user=user)
        if not ensure_place_states.exists():
            for stop in route.stops.select_related("place"):
                UserPlaceState.objects.create(user=user, place=stop.place, last_seen_route=route)

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
                kwargs={"route_id": route.id, "stop_id": "stop-a"},
            )
        )

        self.assertEqual(response.status_code, 200)
        route.refresh_from_db()
        self.assertEqual(route.stops.get(place__source_ref="stop-a").state, ROUTE_STOP_STATE_EXCLUDED)
        self.assertEqual(
            [place["stop_id"] for place in response.data["route"]["places_to_pass"]],
            ["stop-b"],
        )
        self.assertTrue(UserPlaceState.objects.filter(user=user, place__source_ref="stop-a").exists())

    def test_get_current_route_returns_latest_relational_route(self):
        user = User.objects.create_user(
            username="current-user",
            email="current@example.com",
            password="secret123",
        )
        self.client.force_authenticate(user=user)
        older_result = self._build_result(
            places_to_pass=[
                self._make_route_poi(
                    stop_id="older-stop",
                    name="MASP",
                    category="culture",
                    lat=-23.561414,
                    lng=-46.655881,
                    waypoint_order=1,
                )
            ]
        )
        latest_result = self._build_result(
            places_to_pass=[
                self._make_route_poi(
                    stop_id="latest-stop",
                    name="Japan House",
                    category="culture",
                    lat=-23.5701,
                    lng=-46.6458,
                    waypoint_order=1,
                )
            ]
        )
        self._create_cached_route(user=user, base_result=older_result)
        latest_route = self._create_cached_route(user=user, base_result=latest_result)

        response = self.client.get(reverse("tour-route-current"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["route"]["saved_route_id"], latest_route.id)
        self.assertEqual(response.data["route"]["places_to_pass"][0]["stop_id"], "latest-stop")

    def test_get_places_returns_current_then_recent_then_excluded(self):
        user = User.objects.create_user(
            username="places-user",
            email="places@example.com",
            password="secret123",
        )
        self.client.force_authenticate(user=user)
        current_result = self._build_result(
            places_to_pass=[
                self._make_route_poi(
                    stop_id="stop-active",
                    name="MASP",
                    category="culture",
                    lat=-23.561414,
                    lng=-46.655881,
                    waypoint_order=1,
                ),
                self._make_route_poi(
                    stop_id="stop-visited",
                    name="SESC Avenida Paulista",
                    category="culture",
                    lat=-23.5708,
                    lng=-46.6464,
                    included_in_route=False,
                    waypoint_order=None,
                    state=TOUR_ROUTE_STOP_STATE_VISITED,
                ),
            ]
        )
        route = self._create_cached_route(user=user, base_result=current_result, current_result=current_result)
        recent_place = Place.objects.create(
            slug="japan-house-extra",
            category_id=self._ensure_category("culture").id,
            name="Japan House",
            source="overpass",
            source_ref="stop-recent",
            location=Point(-46.6458, -23.5701, srid=4326),
        )
        excluded_place = Place.objects.create(
            slug="trianon-extra",
            category_id=self._ensure_category("park").id,
            name="Parque Trianon",
            source="overpass",
            source_ref="stop-excluded",
            location=Point(-46.6530, -23.5611, srid=4326),
        )
        TourRouteStop.objects.create(
            route=route,
            place=excluded_place,
            display_order=3,
            state=ROUTE_STOP_STATE_EXCLUDED,
            source="overpass",
            distance_from_route_m=12,
        )

        now = timezone.now()
        UserPlaceState.objects.update_or_create(
            user=user,
            place=route.stops.get(place__source_ref="stop-active").place,
            defaults={"last_seen_route": route},
        )
        visited_state, _ = UserPlaceState.objects.update_or_create(
            user=user,
            place=route.stops.get(place__source_ref="stop-visited").place,
            defaults={"is_visited": True, "visited_at": now, "last_seen_route": route},
        )
        recent_state = UserPlaceState.objects.create(
            user=user,
            place=recent_place,
            last_seen_route=route,
        )
        excluded_state = UserPlaceState.objects.create(
            user=user,
            place=excluded_place,
            last_seen_route=route,
        )
        UserPlaceState.objects.filter(id=visited_state.id).update(last_seen_at=now.replace(hour=11, minute=0, second=0, microsecond=0))
        UserPlaceState.objects.filter(id=recent_state.id).update(last_seen_at=now.replace(hour=10, minute=0, second=0, microsecond=0))
        UserPlaceState.objects.filter(id=excluded_state.id).update(last_seen_at=now.replace(hour=12, minute=0, second=0, microsecond=0))

        response = self.client.get(reverse("tour-route-places"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["stop_id"] for item in response.data],
            ["stop-active", "stop-visited", "stop-recent", "stop-excluded"],
        )
        self.assertTrue(response.data[0]["is_in_current_route"])
        self.assertTrue(response.data[3]["is_excluded_from_current_route"])

    @patch("tour_routes.views.build_default_planner")
    def test_patch_global_visited_updates_current_route(self, mock_build_planner):
        user = User.objects.create_user(
            username="global-visited-user",
            email="global@example.com",
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
                )
            ]
        )
        route = self._create_cached_route(user=user, base_result=base_result)
        UserPlaceState.objects.update_or_create(
            user=user,
            place=route.stops.get().place,
            defaults={"is_visited": False, "last_seen_route": route},
        )

        rebuilt_result = self._build_result(
            places_to_pass=[
                self._make_route_poi(
                    stop_id="stop-a",
                    name="MASP",
                    category="culture",
                    lat=-23.561414,
                    lng=-46.655881,
                    included_in_route=False,
                    waypoint_order=None,
                    state=TOUR_ROUTE_STOP_STATE_VISITED,
                )
            ]
        )
        planner = Mock()
        planner.rebuild_from_payload.return_value = (
            rebuilt_result,
            GeoJsonMapBuilder().build(rebuilt_result),
        )
        mock_build_planner.return_value = planner

        response = self.client.patch(
            reverse("tour-route-place-visited", kwargs={"stop_id": "stop-a"}),
            data={"visited": True},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["is_visited"])
        route.refresh_from_db()
        self.assertEqual(route.stops.get(place__source_ref="stop-a").state, TOUR_ROUTE_STOP_STATE_VISITED)

    @patch("tour_routes.views.build_poi_detail_fetcher")
    def test_get_poi_detail_fetches_and_caches_into_canonical_place(self, mock_build_fetcher):
        place = Place.objects.create(
            slug="japan-house",
            category_id=self._ensure_category("culture").id,
            name="Japan House",
            source="overpass",
            source_ref="japan-house-stop",
            location=Point(-46.6458, -23.5701, srid=4326),
            osm_type="way",
            osm_id=123,
        )
        fetcher = Mock()

        def hydrate(record):
            record.address = "Avenida Paulista, 52, Sao Paulo"
            record.summary = "Centro cultural da Avenida Paulista."
            record.source_url = "https://pt.wikipedia.org/wiki/Japan_House"
            record.detail_status = "complete"
            record.details_fetched_at = timezone.now()
            record.save(
                update_fields=[
                    "address",
                    "summary",
                    "source_url",
                    "detail_status",
                    "details_fetched_at",
                    "updated_at",
                ]
            )
            return record

        fetcher.hydrate.side_effect = hydrate
        mock_build_fetcher.return_value = fetcher

        response = self.client.get(
            reverse("tour-route-poi-detail", kwargs={"stop_id": "japan-house-stop"})
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["summary"], "Centro cultural da Avenida Paulista.")
        place.refresh_from_db()
        self.assertEqual(place.detail_status, "complete")

    def _ensure_category(self, slug: str):
        from places.catalog import get_or_create_place_category

        return get_or_create_place_category(slug)

    def test_get_preferences_returns_defaults_without_saved_row(self):
        user = User.objects.create_user(
            username="preferences-user",
            email="preferences@example.com",
            password="secret123",
        )
        self.client.force_authenticate(user=user)

        response = self.client.get(reverse("tour-route-preferences"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data,
            {
                "include_culture": True,
                "include_park": True,
                "include_food": True,
                "poi_spacing_m": TOUR_ROUTE_DEFAULT_POI_SPACING_M,
                "max_search_radius_m": TOUR_ROUTE_DEFAULT_MAX_SEARCH_RADIUS_M,
            },
        )
        self.assertFalse(UserRouteSearchPreference.objects.filter(user=user).exists())

    def test_patch_preferences_persists_valid_values(self):
        user = User.objects.create_user(
            username="preferences-update-user",
            email="preferences-update@example.com",
            password="secret123",
        )
        self.client.force_authenticate(user=user)

        response = self.client.patch(
            reverse("tour-route-preferences"),
            data={
                "include_culture": True,
                "include_park": False,
                "include_food": True,
                "poi_spacing_m": 150,
                "max_search_radius_m": 400,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["poi_spacing_m"], 150)
        self.assertEqual(response.data["max_search_radius_m"], 400)
        preferences = UserRouteSearchPreference.objects.get(user=user)
        self.assertFalse(preferences.include_park)
        self.assertEqual(preferences.poi_spacing_m, 150)
        self.assertEqual(preferences.max_search_radius_m, 400)

    def test_patch_preferences_rejects_all_categories_disabled(self):
        user = User.objects.create_user(
            username="preferences-invalid-user",
            email="preferences-invalid@example.com",
            password="secret123",
        )
        self.client.force_authenticate(user=user)

        response = self.client.patch(
            reverse("tour-route-preferences"),
            data={
                "include_culture": False,
                "include_park": False,
                "include_food": False,
                "poi_spacing_m": 100,
                "max_search_radius_m": 250,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Ative pelo menos uma categoria", str(response.data))
        self.assertFalse(UserRouteSearchPreference.objects.filter(user=user).exists())

    def test_cache_key_changes_when_preferences_change(self):
        base_key, base_payload = build_search_cache_key(
            origin_input={"address": "Av. Paulista, 1578, Sao Paulo"},
            destination_input={"address": "Av. Paulista, 2300, Sao Paulo"},
            search_preferences={
                "include_culture": True,
                "include_park": True,
                "include_food": True,
                "poi_spacing_m": 100,
                "max_search_radius_m": 250,
            },
        )
        variant_key, variant_payload = build_search_cache_key(
            origin_input={"address": "Av. Paulista, 1578, Sao Paulo"},
            destination_input={"address": "Av. Paulista, 2300, Sao Paulo"},
            search_preferences={
                "include_culture": True,
                "include_park": False,
                "include_food": True,
                "poi_spacing_m": 150,
                "max_search_radius_m": 400,
            },
        )

        self.assertNotEqual(base_key, variant_key)
        self.assertNotEqual(base_payload["preferences"], variant_payload["preferences"])

    @patch("tour_routes.views.build_default_planner")
    def test_authenticated_post_uses_saved_preferences_on_new_search(self, mock_build_planner):
        user = User.objects.create_user(
            username="preferences-applied-user",
            email="preferences-applied@example.com",
            password="secret123",
        )
        UserRouteSearchPreference.objects.create(
            user=user,
            include_culture=True,
            include_park=False,
            include_food=True,
            poi_spacing_m=75,
            max_search_radius_m=150,
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
        planner.plan.assert_called_once()
        search_preferences = planner.plan.call_args.kwargs["search_preferences"]
        self.assertTrue(search_preferences.include_culture)
        self.assertFalse(search_preferences.include_park)
        self.assertTrue(search_preferences.include_food)
        self.assertEqual(search_preferences.poi_spacing_m, 75)
        self.assertEqual(search_preferences.max_search_radius_m, 150)
