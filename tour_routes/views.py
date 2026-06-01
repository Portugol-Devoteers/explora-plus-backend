from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .constants import (
    TOUR_ROUTE_DETAIL_STATUS_PENDING,
    TOUR_ROUTE_STOP_STATE_VISITED,
)
from .authentication import OptionalJWTAuthentication
from .models import SavedTourRoute, TourRouteCache, TourRoutePoiDetail
from .persistence import (
    build_search_cache_key,
    bump_cache_hit,
    clone_response_payload,
    create_or_update_cache,
    create_saved_route,
    upsert_poi_detail_stubs,
    update_saved_route_snapshot,
    with_saved_route_id,
)
from .serializers import (
    SavedTourRouteStopStateSerializer,
    TourRouteRequestSerializer,
    serialize_poi_detail,
    serialize_result,
)
from .services.exceptions import TourRouteError
from .services.poi_details import build_poi_detail_fetcher
from .services.planner import build_default_planner


class TourRouteView(APIView):
    authentication_classes = [OptionalJWTAuthentication]
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = TourRouteRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        origin_input = serializer.validated_data["origin"]
        destination_input = serializer.validated_data["destination"]
        cache_key, canonical_payload = build_search_cache_key(
            origin_input=origin_input,
            destination_input=destination_input,
        )
        cache = TourRouteCache.objects.filter(cache_key=cache_key).first()

        if cache is None or _should_refresh_cache(cache):
            planner = build_default_planner()
            try:
                result, map_payload = planner.plan(
                    origin_input=origin_input,
                    destination_input=destination_input,
                )
            except TourRouteError as exc:
                return Response({"detail": str(exc)}, status=exc.status_code)

            response_payload = serialize_result(result, map_payload, saved_route_id=None)
            upsert_poi_detail_stubs(result.places_to_pass)
            cache = create_or_update_cache(
                cache_key=cache_key,
                canonical_payload=canonical_payload,
                origin_query=_endpoint_query(origin_input),
                destination_query=_endpoint_query(destination_input),
                route_payload=response_payload["route"],
                map_payload=response_payload["map"],
            )
        else:
            bump_cache_hit(cache)
            response_payload = clone_response_payload(
                cache.route_payload,
                cache.map_payload,
            )

        if request.user.is_authenticated:
            saved_route = create_saved_route(
                user=request.user,
                cache=cache,
                origin_query=_endpoint_query(origin_input),
                destination_query=_endpoint_query(destination_input),
                route_payload=response_payload["route"],
                map_payload=response_payload["map"],
            )
            response_payload = with_saved_route_id(
                response_payload["route"],
                response_payload["map"],
                saved_route.id,
            )

        return Response(response_payload)


class SavedTourRouteStopDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, route_id: int, stop_id: str):
        saved_route = get_object_or_404(
            SavedTourRoute.objects.select_related("cache"),
            id=route_id,
            user=request.user,
        )

        base_route_payload = saved_route.cache.route_payload
        all_stop_ids = {
            place.get("stop_id")
            for place in base_route_payload.get("places_to_pass", [])
        }
        if stop_id not in all_stop_ids:
            return Response({"detail": "Parada nao encontrada nesta rota."}, status=404)

        excluded_stop_ids = list(saved_route.excluded_stop_ids or [])
        visited_stop_ids = [
            current_stop_id
            for current_stop_id in (saved_route.visited_stop_ids or [])
            if current_stop_id != stop_id
        ]
        if stop_id in excluded_stop_ids:
            return Response(
                with_saved_route_id(
                    saved_route.route_payload,
                    saved_route.map_payload,
                    saved_route.id,
                )
            )

        excluded_stop_ids.append(stop_id)

        planner = build_default_planner()
        try:
            result, map_payload = planner.rebuild_from_payload(
                route_payload=base_route_payload,
                excluded_stop_ids=excluded_stop_ids,
                visited_stop_ids=visited_stop_ids,
            )
        except TourRouteError as exc:
            return Response({"detail": str(exc)}, status=exc.status_code)

        response_payload = update_saved_route_snapshot(
            saved_route=saved_route,
            excluded_stop_ids=excluded_stop_ids,
            visited_stop_ids=visited_stop_ids,
            route_payload=serialize_result(
                result,
                map_payload,
                saved_route_id=saved_route.id,
            )["route"],
            map_payload=map_payload,
        )
        return Response(response_payload)


class SavedTourRouteStopStateView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, route_id: int, stop_id: str):
        serializer = SavedTourRouteStopStateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        saved_route = get_object_or_404(
            SavedTourRoute.objects.select_related("cache"),
            id=route_id,
            user=request.user,
        )

        base_route_payload = saved_route.cache.route_payload
        all_stop_ids = {
            place.get("stop_id")
            for place in base_route_payload.get("places_to_pass", [])
        }
        if stop_id not in all_stop_ids:
            return Response({"detail": "Parada nao encontrada nesta rota."}, status=404)

        excluded_stop_ids = list(saved_route.excluded_stop_ids or [])
        if stop_id in excluded_stop_ids:
            return Response({"detail": "Parada removida da rota."}, status=404)

        next_state = serializer.validated_data["state"]
        visited_stop_ids = list(saved_route.visited_stop_ids or [])
        is_visited = stop_id in visited_stop_ids
        wants_visited = next_state == TOUR_ROUTE_STOP_STATE_VISITED

        if is_visited == wants_visited:
            return Response(
                with_saved_route_id(
                    saved_route.route_payload,
                    saved_route.map_payload,
                    saved_route.id,
                )
            )

        if wants_visited:
            visited_stop_ids.append(stop_id)
        else:
            visited_stop_ids = [
                current_stop_id
                for current_stop_id in visited_stop_ids
                if current_stop_id != stop_id
            ]

        planner = build_default_planner()
        try:
            result, map_payload = planner.rebuild_from_payload(
                route_payload=base_route_payload,
                excluded_stop_ids=excluded_stop_ids,
                visited_stop_ids=visited_stop_ids,
            )
        except TourRouteError as exc:
            return Response({"detail": str(exc)}, status=exc.status_code)

        response_payload = update_saved_route_snapshot(
            saved_route=saved_route,
            excluded_stop_ids=excluded_stop_ids,
            visited_stop_ids=visited_stop_ids,
            route_payload=serialize_result(
                result,
                map_payload,
                saved_route_id=saved_route.id,
            )["route"],
            map_payload=map_payload,
        )
        return Response(response_payload)


class TourRoutePoiDetailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, stop_id: str):
        poi_detail = get_object_or_404(TourRoutePoiDetail, stop_id=stop_id)
        if _should_fetch_poi_detail(poi_detail):
            poi_detail = build_poi_detail_fetcher().hydrate(poi_detail)
        return Response(serialize_poi_detail(poi_detail))


def _endpoint_query(endpoint_input: dict) -> str:
    address = endpoint_input.get("address")
    if address:
        return str(address).strip()

    location = endpoint_input["location"]
    return f'{float(location["lat"]):.6f},{float(location["lng"]):.6f}'


def _should_refresh_cache(cache: TourRouteCache) -> bool:
    route_payload = cache.route_payload or {}
    places = route_payload.get("places_to_pass") or []
    mode = route_payload.get("mode")
    return mode == "direct_fallback" or len(places) == 0


def _should_fetch_poi_detail(poi_detail: TourRoutePoiDetail) -> bool:
    if poi_detail.details_fetched_at is None:
        return True
    if poi_detail.detail_status == TOUR_ROUTE_DETAIL_STATUS_PENDING:
        return True
    return not any(
        [
            poi_detail.address,
            poi_detail.summary,
            poi_detail.image_url,
            poi_detail.source_url,
            poi_detail.website,
            poi_detail.opening_hours,
        ]
    )
