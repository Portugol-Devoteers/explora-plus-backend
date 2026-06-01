from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import SavedTourRoute, TourRouteCache
from .persistence import (
    build_search_cache_key,
    bump_cache_hit,
    clone_response_payload,
    create_or_update_cache,
    create_saved_route,
    update_saved_route_snapshot,
    with_saved_route_id,
)
from .serializers import TourRouteRequestSerializer, serialize_result
from .services.exceptions import TourRouteError
from .services.planner import build_default_planner


class TourRouteView(APIView):
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

        if cache is None:
            planner = build_default_planner()
            try:
                result, map_payload = planner.plan(
                    origin_input=origin_input,
                    destination_input=destination_input,
                )
            except TourRouteError as exc:
                return Response({"detail": str(exc)}, status=exc.status_code)

            response_payload = serialize_result(result, map_payload, saved_route_id=None)
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
            )
        except TourRouteError as exc:
            return Response({"detail": str(exc)}, status=exc.status_code)

        response_payload = update_saved_route_snapshot(
            saved_route=saved_route,
            excluded_stop_ids=excluded_stop_ids,
            route_payload=serialize_result(
                result,
                map_payload,
                saved_route_id=saved_route.id,
            )["route"],
            map_payload=map_payload,
        )
        return Response(response_payload)


def _endpoint_query(endpoint_input: dict) -> str:
    address = endpoint_input.get("address")
    if address:
        return str(address).strip()

    location = endpoint_input["location"]
    return f'{float(location["lat"]):.6f},{float(location["lng"]):.6f}'
