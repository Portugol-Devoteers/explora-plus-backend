from __future__ import annotations

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

        places_to_pass = self.poi_selector.select(
            poi_candidates, route_distance_m=direct_route_path.distance_m
        )

        tour_route_path = None
        included_waypoint_indices: list[int] = []
        if places_to_pass:
            tour_route_path = self._build_free_walk_route(
                origin=origin,
                destination=destination,
                places_to_pass=places_to_pass,
            )
            included_waypoint_indices = list(range(len(places_to_pass)))

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
            places_to_pass=self._annotate_places(
                places_to_pass,
                included_waypoint_indices=included_waypoint_indices,
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

    def _annotate_places(
        self,
        places_to_pass,
        *,
        included_waypoint_indices: list[int],
    ) -> list[RoutePoi]:
        waypoint_order_by_index = {
            index: order
            for order, index in enumerate(included_waypoint_indices, start=1)
        }

        annotated_places: list[RoutePoi] = []
        for index, poi in enumerate(places_to_pass):
            annotated_places.append(
                RoutePoi(
                    name=poi.name,
                    category=poi.category,
                    source=poi.source,
                    location=poi.location,
                    distance_from_route_m=poi.distance_from_route_m,
                    progress_m=poi.progress_m,
                    priority=poi.priority,
                    included_in_route=index in waypoint_order_by_index,
                    waypoint_order=waypoint_order_by_index.get(index),
                )
            )
        return annotated_places

    def _build_free_walk_route(
        self,
        *,
        origin: ResolvedPoint,
        destination: ResolvedPoint,
        places_to_pass,
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


def build_default_planner() -> TourRoutePlanner:
    return TourRoutePlanner()
