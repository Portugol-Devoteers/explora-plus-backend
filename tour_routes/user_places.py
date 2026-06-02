from __future__ import annotations

from django.utils import timezone

from .models import SavedTourRoute, TourRoutePoiDetail, UserTourPlace
from .persistence import upsert_poi_detail_stubs_from_route_payload


def get_latest_saved_route(user) -> SavedTourRoute | None:
    return (
        SavedTourRoute.objects.select_related("cache")
        .filter(user=user)
        .order_by("-created_at", "-id")
        .first()
    )


def ensure_user_tour_places_from_route_payload(
    *,
    user,
    route_payload: dict,
    saved_route: SavedTourRoute | None = None,
    touch_existing: bool = True,
) -> list[UserTourPlace]:
    upsert_poi_detail_stubs_from_route_payload(route_payload)
    places: list[UserTourPlace] = []
    for place in route_payload.get("places_to_pass", []):
        stop_id = place.get("stop_id")
        if not stop_id:
            continue

        poi_detail = TourRoutePoiDetail.objects.filter(stop_id=stop_id).first()
        if poi_detail is None:
            continue

        user_place, created = UserTourPlace.objects.get_or_create(
            user=user,
            poi_detail=poi_detail,
            defaults={
                "is_visited": bool(place.get("state") == "visited"),
                "visited_at": timezone.now() if place.get("state") == "visited" else None,
                "seen_count": 1,
                "last_seen_route": saved_route,
            },
        )
        if created:
            places.append(user_place)
            continue

        if touch_existing:
            user_place.seen_count += 1
            user_place.last_seen_route = saved_route
            user_place.save(
                update_fields=["seen_count", "last_seen_route", "last_seen_at"]
            )
        places.append(user_place)

    return places


def ensure_user_tour_place_for_stop(
    *,
    user,
    stop_id: str,
    route_payload: dict,
    saved_route: SavedTourRoute | None = None,
) -> UserTourPlace | None:
    ensure_user_tour_places_from_route_payload(
        user=user,
        route_payload=route_payload,
        saved_route=saved_route,
        touch_existing=False,
    )
    return (
        UserTourPlace.objects.select_related("poi_detail")
        .filter(user=user, poi_detail__stop_id=stop_id)
        .first()
    )


def get_visited_stop_ids_for_route_payload(*, user, route_payload: dict) -> list[str]:
    stop_ids = [
        place.get("stop_id")
        for place in route_payload.get("places_to_pass", [])
        if place.get("stop_id")
    ]
    if not stop_ids:
        return []

    return list(
        UserTourPlace.objects.filter(
            user=user,
            poi_detail__stop_id__in=stop_ids,
            is_visited=True,
        ).values_list("poi_detail__stop_id", flat=True)
    )


def set_user_tour_place_visited(
    *,
    user,
    stop_id: str,
    visited: bool,
    route_payload: dict | None = None,
    saved_route: SavedTourRoute | None = None,
) -> UserTourPlace | None:
    if route_payload is not None:
        ensure_user_tour_place_for_stop(
            user=user,
            stop_id=stop_id,
            route_payload=route_payload,
            saved_route=saved_route,
        )

    user_place = (
        UserTourPlace.objects.select_related("poi_detail")
        .filter(user=user, poi_detail__stop_id=stop_id)
        .first()
    )
    if user_place is None:
        return None

    user_place.is_visited = visited
    user_place.visited_at = timezone.now() if visited else None
    user_place.save(update_fields=["is_visited", "visited_at", "last_seen_at"])
    return user_place


def build_user_place_library(*, user) -> list[dict]:
    current_saved_route = get_latest_saved_route(user)
    active_lookup: dict[str, int] = {}
    excluded_ids: set[str] = set()

    if current_saved_route is not None:
        ensure_user_tour_places_from_route_payload(
            user=user,
            route_payload=current_saved_route.cache.route_payload,
            saved_route=current_saved_route,
            touch_existing=False,
        )
        excluded_ids = set(current_saved_route.excluded_stop_ids or [])
        for place in current_saved_route.route_payload.get("places_to_pass", []):
            stop_id = place.get("stop_id")
            waypoint_order = place.get("waypoint_order")
            if (
                stop_id
                and bool(place.get("included_in_route"))
                and isinstance(waypoint_order, int)
            ):
                active_lookup[stop_id] = waypoint_order

    payloads = []
    queryset = (
        UserTourPlace.objects.select_related("poi_detail")
        .filter(user=user)
        .order_by("-last_seen_at", "-id")
    )
    for user_place in queryset:
        stop_id = user_place.poi_detail.stop_id
        payloads.append(
            {
                "stop_id": stop_id,
                "name": user_place.poi_detail.name,
                "category": user_place.poi_detail.category,
                "image_url": user_place.poi_detail.image_url or None,
                "address": user_place.poi_detail.address,
                "summary": user_place.poi_detail.summary,
                "is_visited": user_place.is_visited,
                "is_in_current_route": stop_id in active_lookup,
                "is_excluded_from_current_route": stop_id in excluded_ids,
                "current_route_order": active_lookup.get(stop_id),
                "last_seen_at": user_place.last_seen_at,
            }
        )

    return sorted(payloads, key=_library_sort_key)


def sync_saved_route_with_user_places(
    *,
    saved_route: SavedTourRoute,
    planner,
    serialize_result,
) -> dict:
    visited_stop_ids = get_visited_stop_ids_for_route_payload(
        user=saved_route.user,
        route_payload=saved_route.cache.route_payload,
    )
    result, map_payload = planner.rebuild_from_payload(
        route_payload=saved_route.cache.route_payload,
        excluded_stop_ids=list(saved_route.excluded_stop_ids or []),
        visited_stop_ids=visited_stop_ids,
    )
    route_payload = serialize_result(
        result,
        map_payload,
        saved_route_id=saved_route.id,
    )["route"]
    return {
        "visited_stop_ids": visited_stop_ids,
        "route_payload": route_payload,
        "map_payload": map_payload,
    }


def _library_sort_key(item: dict) -> tuple[int, int, float]:
    if item["is_in_current_route"]:
        return (0, int(item["current_route_order"] or 0), 0.0)
    if item["is_excluded_from_current_route"]:
        return (2, 0, -item["last_seen_at"].timestamp())
    return (1, 0, -item["last_seen_at"].timestamp())
