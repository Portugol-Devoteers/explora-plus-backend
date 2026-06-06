from __future__ import annotations

import copy
import hashlib
import json

from django.contrib.gis.geos import LineString, Point

from core.domain import ROUTE_STOP_STATE_ACTIVE, ROUTE_STOP_STATE_EXCLUDED, ROUTE_STOP_STATE_VISITED
from places.catalog import upsert_places_from_route_payload

from .models import RouteSearchCache, TourRoute, TourRouteStop


def build_search_cache_key(
    *,
    origin_input: dict,
    destination_input: dict,
    search_preferences: dict | None = None,
) -> tuple[str, dict]:
    canonical_payload = {
        "origin": _canonicalize_endpoint(origin_input),
        "destination": _canonicalize_endpoint(destination_input),
        "preferences": _canonicalize_preferences(search_preferences or {}),
    }
    serialized = json.dumps(
        canonical_payload,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest(), canonical_payload


def clone_response_payload(route_payload: dict, map_payload: dict) -> dict:
    return {
        "route": copy.deepcopy(route_payload),
        "map": copy.deepcopy(map_payload),
    }


def with_saved_route_id(route_payload: dict, map_payload: dict, saved_route_id: int | None) -> dict:
    payload = clone_response_payload(route_payload, map_payload)
    payload["route"]["saved_route_id"] = saved_route_id
    return payload


def create_or_update_cache(
    *,
    cache_key: str,
    canonical_payload: dict,
    origin_query: str,
    destination_query: str,
    route_payload: dict,
    map_payload: dict,
) -> RouteSearchCache:
    cache, created = RouteSearchCache.objects.get_or_create(
        cache_key=cache_key,
        defaults={
            "origin_query": origin_query,
            "destination_query": destination_query,
            "search_payload": canonical_payload,
            "route_payload": route_payload,
            "map_payload": map_payload,
            "hit_count": 1,
        },
    )
    if not created:
        cache.origin_query = origin_query
        cache.destination_query = destination_query
        cache.search_payload = canonical_payload
        cache.route_payload = route_payload
        cache.map_payload = map_payload
        cache.hit_count += 1
        cache.save(
            update_fields=[
                "origin_query",
                "destination_query",
                "search_payload",
                "route_payload",
                "map_payload",
                "hit_count",
                "updated_at",
            ]
        )
    return cache


def bump_cache_hit(cache: RouteSearchCache) -> None:
    cache.hit_count += 1
    cache.save(update_fields=["hit_count", "updated_at"])


def create_tour_route(
    *,
    user,
    search_cache: RouteSearchCache,
    origin_query: str,
    destination_query: str,
    base_route_payload: dict,
    current_route_payload: dict,
    excluded_stop_ids: list[str] | None = None,
    visited_stop_ids: list[str] | None = None,
) -> TourRoute:
    route = TourRoute.objects.create(
        user=user,
        search_cache=search_cache,
        origin_query=origin_query,
        destination_query=destination_query,
        origin_label=current_route_payload["origin"]["label"],
        destination_label=current_route_payload["destination"]["label"],
        origin_location=_point_from_payload(current_route_payload["origin"]["location"]),
        destination_location=_point_from_payload(
            current_route_payload["destination"]["location"]
        ),
        mode=current_route_payload["mode"],
        distance_m=int(current_route_payload["distance_m"]),
        duration_s=int(current_route_payload["duration_s"]),
        direct_distance_m=int(current_route_payload["direct_route"]["distance_m"]),
        direct_duration_s=int(current_route_payload["direct_route"]["duration_s"]),
        route_geometry=_line_string_from_points(
            current_route_payload.get("polyline_points", [])
        ),
        direct_route_geometry=_line_string_from_points(
            current_route_payload["direct_route"].get("polyline_points", [])
        ),
    )
    _replace_route_stops(
        route=route,
        base_route_payload=base_route_payload,
        current_route_payload=current_route_payload,
        excluded_stop_ids=list(excluded_stop_ids or []),
        visited_stop_ids=list(visited_stop_ids or []),
    )
    return route


def update_tour_route_snapshot(
    *,
    route: TourRoute,
    base_route_payload: dict,
    current_route_payload: dict,
    excluded_stop_ids: list[str],
    visited_stop_ids: list[str],
) -> TourRoute:
    route.origin_label = current_route_payload["origin"]["label"]
    route.destination_label = current_route_payload["destination"]["label"]
    route.origin_location = _point_from_payload(current_route_payload["origin"]["location"])
    route.destination_location = _point_from_payload(
        current_route_payload["destination"]["location"]
    )
    route.mode = current_route_payload["mode"]
    route.distance_m = int(current_route_payload["distance_m"])
    route.duration_s = int(current_route_payload["duration_s"])
    route.direct_distance_m = int(current_route_payload["direct_route"]["distance_m"])
    route.direct_duration_s = int(current_route_payload["direct_route"]["duration_s"])
    route.route_geometry = _line_string_from_points(
        current_route_payload.get("polyline_points", [])
    )
    route.direct_route_geometry = _line_string_from_points(
        current_route_payload["direct_route"].get("polyline_points", [])
    )
    route.save(
        update_fields=[
            "origin_label",
            "destination_label",
            "origin_location",
            "destination_location",
            "mode",
            "distance_m",
            "duration_s",
            "direct_distance_m",
            "direct_duration_s",
            "route_geometry",
            "direct_route_geometry",
            "updated_at",
        ]
    )
    _replace_route_stops(
        route=route,
        base_route_payload=base_route_payload,
        current_route_payload=current_route_payload,
        excluded_stop_ids=excluded_stop_ids,
        visited_stop_ids=visited_stop_ids,
    )
    return route


def _replace_route_stops(
    *,
    route: TourRoute,
    base_route_payload: dict,
    current_route_payload: dict,
    excluded_stop_ids: list[str],
    visited_stop_ids: list[str],
) -> None:
    places_by_stop_id = upsert_places_from_route_payload(base_route_payload)
    current_place_lookup = {
        place["stop_id"]: place
        for place in current_route_payload.get("places_to_pass", [])
        if place.get("stop_id")
    }
    excluded_set = set(excluded_stop_ids)
    visited_set = set(visited_stop_ids)

    TourRouteStop.objects.filter(route=route).delete()
    stops_to_create: list[TourRouteStop] = []
    for display_order, base_place_payload in enumerate(
        base_route_payload.get("places_to_pass", []),
        start=1,
    ):
        stop_id = base_place_payload.get("stop_id")
        if not stop_id:
            continue
        place = places_by_stop_id.get(stop_id)
        if place is None:
            continue

        current_payload = current_place_lookup.get(stop_id, base_place_payload)
        if stop_id in excluded_set:
            state = ROUTE_STOP_STATE_EXCLUDED
            waypoint_order = None
        elif stop_id in visited_set or current_payload.get("state") == ROUTE_STOP_STATE_VISITED:
            state = ROUTE_STOP_STATE_VISITED
            waypoint_order = None
        else:
            state = ROUTE_STOP_STATE_ACTIVE
            waypoint_order = current_payload.get("waypoint_order")

        stops_to_create.append(
            TourRouteStop(
                route=route,
                place=place,
                display_order=display_order,
                waypoint_order=waypoint_order if isinstance(waypoint_order, int) else None,
                state=state,
                source=current_payload.get("source", base_place_payload.get("source", "")),
                distance_from_route_m=int(
                    round(
                        float(
                            current_payload.get(
                                "distance_from_route_m",
                                base_place_payload.get("distance_from_route_m", 0),
                            )
                        )
                    )
                ),
            )
        )

    if stops_to_create:
        TourRouteStop.objects.bulk_create(stops_to_create)


def _canonicalize_endpoint(endpoint_input: dict) -> dict:
    address = endpoint_input.get("address")
    if address:
        return {"address": " ".join(str(address).strip().casefold().split())}

    location = endpoint_input["location"]
    return {
        "location": {
            "lat": round(float(location["lat"]), 6),
            "lng": round(float(location["lng"]), 6),
        }
    }


def _canonicalize_preferences(search_preferences: dict) -> dict:
    return {
        "include_culture": bool(search_preferences.get("include_culture", True)),
        "include_park": bool(search_preferences.get("include_park", True)),
        "include_food": bool(search_preferences.get("include_food", True)),
        "poi_spacing_m": int(search_preferences.get("poi_spacing_m", 100)),
        "max_search_radius_m": int(search_preferences.get("max_search_radius_m", 250)),
    }


def _point_from_payload(location_payload: dict) -> Point:
    return Point(
        float(location_payload["lng"]),
        float(location_payload["lat"]),
        srid=4326,
    )


def _line_string_from_points(points: list[dict]) -> LineString | None:
    coordinates = [
        (float(point["lng"]), float(point["lat"]))
        for point in points
        if point is not None
    ]
    if not coordinates:
        return None
    if len(coordinates) == 1:
        coordinates = [coordinates[0], coordinates[0]]
    return LineString(*coordinates, srid=4326)
