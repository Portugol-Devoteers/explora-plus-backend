from __future__ import annotations

import copy
import hashlib
import json

from .models import SavedTourRoute, TourRouteCache, TourRoutePoiDetail


def build_search_cache_key(*, origin_input: dict, destination_input: dict) -> tuple[str, dict]:
    canonical_payload = {
        "origin": _canonicalize_endpoint(origin_input),
        "destination": _canonicalize_endpoint(destination_input),
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
) -> TourRouteCache:
    cache, created = TourRouteCache.objects.get_or_create(
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


def bump_cache_hit(cache: TourRouteCache) -> None:
    cache.hit_count += 1
    cache.save(update_fields=["hit_count", "updated_at"])


def create_saved_route(
    *,
    user,
    cache: TourRouteCache,
    origin_query: str,
    destination_query: str,
    route_payload: dict,
    map_payload: dict,
    visited_stop_ids: list[str] | None = None,
) -> SavedTourRoute:
    saved_route = SavedTourRoute.objects.create(
        user=user,
        cache=cache,
        origin_query=origin_query,
        destination_query=destination_query,
        origin_label=route_payload["origin"]["label"],
        destination_label=route_payload["destination"]["label"],
        visited_stop_ids=list(visited_stop_ids or []),
        distance_m=int(route_payload["distance_m"]),
        duration_s=int(route_payload["duration_s"]),
    )
    response_payload = with_saved_route_id(route_payload, map_payload, saved_route.id)
    saved_route.route_payload = response_payload["route"]
    saved_route.map_payload = response_payload["map"]
    saved_route.save(update_fields=["route_payload", "map_payload"])
    return saved_route


def update_saved_route_snapshot(
    *,
    saved_route: SavedTourRoute,
    excluded_stop_ids: list[str],
    visited_stop_ids: list[str],
    route_payload: dict,
    map_payload: dict,
) -> dict:
    response_payload = with_saved_route_id(route_payload, map_payload, saved_route.id)
    saved_route.excluded_stop_ids = excluded_stop_ids
    saved_route.visited_stop_ids = visited_stop_ids
    saved_route.origin_label = route_payload["origin"]["label"]
    saved_route.destination_label = route_payload["destination"]["label"]
    saved_route.distance_m = int(route_payload["distance_m"])
    saved_route.duration_s = int(route_payload["duration_s"])
    saved_route.route_payload = response_payload["route"]
    saved_route.map_payload = response_payload["map"]
    saved_route.save(
        update_fields=[
            "excluded_stop_ids",
            "visited_stop_ids",
            "origin_label",
            "destination_label",
            "distance_m",
            "duration_s",
            "route_payload",
            "map_payload",
            "updated_at",
        ]
    )
    return response_payload


def upsert_poi_detail_stubs(route_pois) -> None:
    for poi in route_pois:
        record, created = TourRoutePoiDetail.objects.get_or_create(
            stop_id=poi.stop_id,
            defaults={
                "name": poi.name,
                "category": poi.category,
                "lat": poi.location.lat,
                "lng": poi.location.lng,
                "source": poi.source,
                "osm_type": poi.osm_type or "",
                "osm_id": poi.osm_id,
                "wikidata_id": poi.wikidata_id or "",
                "wikipedia_title": poi.wikipedia_title or "",
                "address": poi.address or "",
                "website": poi.website or "",
                "opening_hours": poi.opening_hours or "",
                "raw_payload": _build_raw_payload(poi.raw_tags),
            },
        )
        if created:
            continue

        update_fields: list[str] = []
        for field_name, value in (
            ("name", poi.name),
            ("category", poi.category),
            ("lat", poi.location.lat),
            ("lng", poi.location.lng),
            ("source", poi.source),
            ("osm_type", poi.osm_type or ""),
            ("osm_id", poi.osm_id),
            ("wikidata_id", poi.wikidata_id or ""),
            ("wikipedia_title", poi.wikipedia_title or ""),
        ):
            if getattr(record, field_name) != value:
                setattr(record, field_name, value)
                update_fields.append(field_name)

        for field_name, value in (
            ("website", poi.website or ""),
            ("opening_hours", poi.opening_hours or ""),
        ):
            if value and getattr(record, field_name) != value:
                setattr(record, field_name, value)
                update_fields.append(field_name)

        if poi.address and not record.address:
            record.address = poi.address
            update_fields.append("address")

        raw_payload = _build_raw_payload(poi.raw_tags)
        if raw_payload and record.raw_payload != raw_payload:
            record.raw_payload = raw_payload
            update_fields.append("raw_payload")

        if update_fields:
            record.save(update_fields=[*update_fields, "updated_at"])


def upsert_poi_detail_stubs_from_route_payload(route_payload: dict) -> None:
    for place in route_payload.get("places_to_pass", []):
        stop_id = place.get("stop_id")
        location = place.get("location") or {}
        if not stop_id:
            continue

        record, created = TourRoutePoiDetail.objects.get_or_create(
            stop_id=stop_id,
            defaults={
                "name": place.get("name", ""),
                "category": place.get("category", ""),
                "lat": float(location.get("lat", 0.0)),
                "lng": float(location.get("lng", 0.0)),
                "source": place.get("source", "cache"),
            },
        )
        if created:
            continue

        update_fields: list[str] = []
        for field_name, value in (
            ("name", place.get("name", "")),
            ("category", place.get("category", "")),
            ("source", place.get("source", "cache")),
        ):
            if value and getattr(record, field_name) != value:
                setattr(record, field_name, value)
                update_fields.append(field_name)

        lat = float(location.get("lat", record.lat))
        lng = float(location.get("lng", record.lng))
        if record.lat != lat:
            record.lat = lat
            update_fields.append("lat")
        if record.lng != lng:
            record.lng = lng
            update_fields.append("lng")

        if update_fields:
            record.save(update_fields=[*update_fields, "updated_at"])


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


def _build_raw_payload(raw_tags: dict[str, str] | None) -> dict:
    if not raw_tags:
        return {}
    return {"tags": raw_tags}
