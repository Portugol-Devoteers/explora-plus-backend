from __future__ import annotations

from tour_routes.types import GeoPoint, ResolvedPoint, TourRouteResult

from .exceptions import PoiSearchError
from .geocoding import NominatimGeocoder
from .map_builder import GeoJsonMapBuilder
from .poi_search import OverpassPoiSearcher
from .poi_selector import PoiSelector
from .routing import OsrmWalkingRouter


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
        route_path = self.router.route(origin, destination)

        try:
            poi_candidates = self.poi_searcher.search(route_path)
        except PoiSearchError:
            poi_candidates = []

        places_to_pass = self.poi_selector.select(
            poi_candidates, route_distance_m=route_path.distance_m
        )
        result = TourRouteResult(
            origin=origin,
            destination=destination,
            route_path=route_path,
            places_to_pass=places_to_pass,
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


def build_default_planner() -> TourRoutePlanner:
    return TourRoutePlanner()
