from __future__ import annotations

import hashlib
from dataclasses import replace

from tour_routes.constants import (
    TOUR_ROUTE_MODE_DIRECT_FALLBACK,
    TOUR_ROUTE_MODE_TOUR,
)
from tour_routes.types import GeoPoint, ResolvedPoint, RoutePath, RoutePoi, TourRouteResult

from .exceptions import PoiSearchError
from .geocoding import NominatimGeocoder
from .geometry import polyline_distance_m
from .map_builder import GeoJsonMapBuilder
from .poi_search import OverpassPoiSearcher
from .poi_selector import PoiSelector
from .routing import OsrmWalkingRouter

FREE_WALKING_SPEED_MPS = 1.35


class TourRoutePlanner:
    def __init__(
        self,
        *,
        geocoder: NominatimGeocoder | None = None,
        router: OsrmWalkingRouter | None = None,
        poi_searcher: OverpassPoiSearcher | None = None,
        poi_selector: PoiSelector | None = None,
        map_builder: GeoJsonMapBuilder | None = None,
    ):
        self.geocoder = geocoder or NominatimGeocoder()
        self.router = router or OsrmWalkingRouter()
        self.poi_searcher = poi_searcher or OverpassPoiSearcher()
        self.poi_selector = poi_selector or PoiSelector()
        self.map_builder = map_builder or GeoJsonMapBuilder()

    def plan(self, *, origin_input: dict, destination_input: dict):
        origin = self._resolve_endpoint(origin_input)
        destination = self._resolve_endpoint(destination_input)
        direct_route_path = self.router.route(origin, destination)

        try:
            poi_candidates = self.poi_searcher.search(direct_route_path)
        except PoiSearchError:
            poi_candidates = []

        selected_candidates = self.poi_selector.select(
            poi_candidates,
            route_distance_m=direct_route_path.distance_m,
        )
        selected_places = [
            self._route_poi_from_candidate(candidate) for candidate in selected_candidates
        ]
        return self._build_result(
            origin=origin,
            destination=destination,
            direct_route_path=direct_route_path,
            places_to_pass=selected_places,
        )

    def rebuild_from_payload(
        self,
        *,
        route_payload: dict,
        excluded_stop_ids: list[str] | None = None,
    ):
        excluded_ids = set(excluded_stop_ids or [])
        origin = self._resolved_point_from_payload(route_payload["origin"])
        destination = self._resolved_point_from_payload(route_payload["destination"])
        direct_route_path = self._route_path_from_summary(route_payload["direct_route"])
        places_to_pass = [
            self._route_poi_from_payload(place_payload)
            for place_payload in route_payload.get("places_to_pass", [])
            if place_payload.get("stop_id") not in excluded_ids
        ]
        return self._build_result(
            origin=origin,
            destination=destination,
            direct_route_path=direct_route_path,
            places_to_pass=places_to_pass,
        )

    def _build_result(
        self,
        *,
        origin: ResolvedPoint,
        destination: ResolvedPoint,
        direct_route_path: RoutePath,
        places_to_pass: list[RoutePoi],
    ):
        tour_route_path = (
            self._build_free_walk_route(
                origin=origin,
                destination=destination,
                places_to_pass=places_to_pass,
            )
            if places_to_pass
            else None
        )

        route_path = tour_route_path or direct_route_path
        mode = (
            TOUR_ROUTE_MODE_TOUR
            if tour_route_path is not None
            else TOUR_ROUTE_MODE_DIRECT_FALLBACK
        )
        result = TourRouteResult(
            origin=origin,
            destination=destination,
            route_path=route_path,
            direct_route_path=direct_route_path,
            tour_route_path=tour_route_path,
            mode=mode,
            places_to_pass=self._resequence_places(
                places_to_pass,
                included_in_route=tour_route_path is not None,
            ),
        )
        map_payload = self.map_builder.build(result)
        return result, map_payload

    def _resolve_endpoint(self, endpoint_input: dict) -> ResolvedPoint:
        address = endpoint_input.get("address")
        if address:
            return self.geocoder.resolve(address)

        location = endpoint_input["location"]
        point = GeoPoint(
            lat=float(location["lat"]),
            lng=float(location["lng"]),
        )
        return ResolvedPoint(
            label=f"{point.lat:.6f}, {point.lng:.6f}",
            location=point,
        )

    def _build_free_walk_route(
        self,
        *,
        origin: ResolvedPoint,
        destination: ResolvedPoint,
        places_to_pass: list[RoutePoi],
    ) -> RoutePath:
        coordinates = [
            origin.location,
            *(place.location for place in places_to_pass),
            destination.location,
        ]
        distance_m = int(round(polyline_distance_m(coordinates)))
        duration_s = int(round(distance_m / FREE_WALKING_SPEED_MPS)) if distance_m else 0
        return RoutePath(
            distance_m=distance_m,
            duration_s=duration_s,
            coordinates=coordinates,
        )

    def _resequence_places(
        self,
        places_to_pass: list[RoutePoi],
        *,
        included_in_route: bool,
    ) -> list[RoutePoi]:
        resequenced: list[RoutePoi] = []
        for index, poi in enumerate(places_to_pass, start=1):
            resequenced.append(
                replace(
                    poi,
                    included_in_route=included_in_route,
                    waypoint_order=index if included_in_route else None,
                )
            )
        return resequenced

    def _route_poi_from_candidate(self, candidate) -> RoutePoi:
        return RoutePoi(
            stop_id=self._build_stop_id(
                name=candidate.name,
                category=candidate.category,
                location=candidate.location,
            ),
            name=candidate.name,
            category=candidate.category,
            source=candidate.source,
            location=candidate.location,
            distance_from_route_m=candidate.distance_from_route_m,
            progress_m=candidate.progress_m,
            priority=candidate.priority,
            included_in_route=False,
            waypoint_order=None,
        )

    def _route_poi_from_payload(self, place_payload: dict) -> RoutePoi:
        location = GeoPoint(
            lat=float(place_payload["location"]["lat"]),
            lng=float(place_payload["location"]["lng"]),
        )
        stop_id = place_payload.get("stop_id") or self._build_stop_id(
            name=place_payload["name"],
            category=place_payload["category"],
            location=location,
        )
        return RoutePoi(
            stop_id=stop_id,
            name=place_payload["name"],
            category=place_payload["category"],
            source=place_payload.get("source", "cache"),
            location=location,
            distance_from_route_m=float(place_payload.get("distance_from_route_m", 0)),
            progress_m=float(place_payload.get("progress_m", 0)),
            priority=0,
            included_in_route=bool(place_payload.get("included_in_route")),
            waypoint_order=place_payload.get("waypoint_order"),
        )

    def _resolved_point_from_payload(self, payload: dict) -> ResolvedPoint:
        return ResolvedPoint(
            label=payload["label"],
            location=GeoPoint(
                lat=float(payload["location"]["lat"]),
                lng=float(payload["location"]["lng"]),
            ),
        )

    def _route_path_from_summary(self, summary: dict) -> RoutePath:
        return RoutePath(
            distance_m=int(summary["distance_m"]),
            duration_s=int(summary["duration_s"]),
            coordinates=[
                GeoPoint(lat=float(point["lat"]), lng=float(point["lng"]))
                for point in summary.get("polyline_points", [])
            ],
        )

    def _build_stop_id(
        self,
        *,
        name: str,
        category: str,
        location: GeoPoint,
    ) -> str:
        raw = (
            f"{name.casefold()}|{category}|"
            f"{location.lat:.6f}|{location.lng:.6f}"
        )
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def build_default_planner() -> TourRoutePlanner:
    return TourRoutePlanner()
