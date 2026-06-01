from __future__ import annotations

from tour_routes.constants import (
    TOUR_ROUTE_MODE_DIRECT_FALLBACK,
    TOUR_ROUTE_MODE_TOUR,
)
from tour_routes.types import GeoPoint, ResolvedPoint, RoutePath, RoutePoi, TourRouteResult

from .exceptions import PoiSearchError, RouteProviderError
from .geocoding import NominatimGeocoder
from .geometry import haversine_distance_m
from .map_builder import GeoJsonMapBuilder
from .poi_search import OverpassPoiSearcher
from .poi_selector import PoiSelector
from .routing import OsrmWalkingRouter

FREE_WALKING_SPEED_MPS = 1.35
SHORT_HOP_MAX_DISTANCE_M = 300.0
MAX_DETAILED_LEG_RATIO = 2.3
MAX_DETAILED_LEG_OVERHEAD_M = 180.0


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
        checkpoints = [
            origin,
            *(
                ResolvedPoint(label=place.name, location=place.location)
                for place in places_to_pass
            ),
            destination,
        ]
        coordinates: list[GeoPoint] = []
        total_distance_m = 0.0
        total_duration_s = 0.0

        for start, end in zip(checkpoints, checkpoints[1:]):
            leg = self._build_leg_route(start=start, end=end)
            total_distance_m += leg.distance_m
            total_duration_s += leg.duration_s

            if not coordinates:
                coordinates.extend(leg.coordinates)
                continue

            coordinates.extend(leg.coordinates[1:])

        return RoutePath(
            distance_m=int(round(total_distance_m)),
            duration_s=int(round(total_duration_s)),
            coordinates=coordinates,
        )

    def _build_leg_route(self, *, start: ResolvedPoint, end: ResolvedPoint) -> RoutePath:
        straight_distance_m = haversine_distance_m(start.location, end.location)

        try:
            detailed_leg = self.router.route(
                start,
                end,
                error_message="Nao foi possivel calcular um trecho da rota turistica.",
            )
        except RouteProviderError:
            return self._build_straight_leg(
                start=start,
                end=end,
                distance_m=straight_distance_m,
            )

        if self._should_use_straight_leg(
            detailed_distance_m=detailed_leg.distance_m,
            straight_distance_m=straight_distance_m,
        ):
            return self._build_straight_leg(
                start=start,
                end=end,
                distance_m=straight_distance_m,
            )

        return detailed_leg

    def _build_straight_leg(
        self,
        *,
        start: ResolvedPoint,
        end: ResolvedPoint,
        distance_m: float,
    ) -> RoutePath:
        duration_s = int(round(distance_m / FREE_WALKING_SPEED_MPS)) if distance_m else 0
        return RoutePath(
            distance_m=int(round(distance_m)),
            duration_s=duration_s,
            coordinates=[start.location, end.location],
        )

    def _should_use_straight_leg(
        self,
        *,
        detailed_distance_m: int,
        straight_distance_m: float,
    ) -> bool:
        if straight_distance_m <= 0:
            return False

        if straight_distance_m > SHORT_HOP_MAX_DISTANCE_M:
            return False

        return (
            detailed_distance_m > straight_distance_m * MAX_DETAILED_LEG_RATIO
            and detailed_distance_m - straight_distance_m >= MAX_DETAILED_LEG_OVERHEAD_M
        )


def build_default_planner() -> TourRoutePlanner:
    return TourRoutePlanner()
