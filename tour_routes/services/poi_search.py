from __future__ import annotations

from urllib.error import HTTPError, URLError

from tour_routes.constants import (
    TOUR_ROUTE_CATEGORY_CULTURE,
    TOUR_ROUTE_CATEGORY_FOOD,
    TOUR_ROUTE_CATEGORY_PARK,
    TOUR_ROUTE_CATEGORY_PRIORITY,
)
from tour_routes.types import GeoPoint, PoiCandidate, RoutePath

from .exceptions import PoiSearchError
from .geometry import expand_bbox, project_point_onto_route
from .http import JsonHttpClient

MAX_DISTANCE_FROM_ROUTE_M = 250.0


class OverpassPoiSearcher:
    endpoint = "https://overpass-api.de/api/interpreter"
    category_priority = TOUR_ROUTE_CATEGORY_PRIORITY

    def __init__(self, client: JsonHttpClient | None = None):
        self.client = client or JsonHttpClient()

    def search(self, route_path: RoutePath) -> list[PoiCandidate]:
        if not route_path.coordinates:
            return []

        bbox = expand_bbox(route_path.coordinates, padding_m=MAX_DISTANCE_FROM_ROUTE_M)
        query = self._build_query(*bbox)

        try:
            payload = self.client.post_text_json(self.endpoint, body=query)
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            raise PoiSearchError("Nao foi possivel buscar pontos de interesse.") from exc

        elements = payload.get("elements")
        if elements is None:
            raise PoiSearchError("O provedor de pontos nao retornou uma resposta valida.")

        candidates: list[PoiCandidate] = []
        for element in elements:
            tags = element.get("tags") or {}
            name = tags.get("name")
            if not name:
                continue

            point = self._extract_point(element)
            if point is None:
                continue

            category = self._classify_category(tags)
            if category is None:
                continue

            distance_from_route_m, progress_m = project_point_onto_route(
                point, route_path.coordinates
            )
            if distance_from_route_m > MAX_DISTANCE_FROM_ROUTE_M:
                continue

            candidates.append(
                PoiCandidate(
                    name=name,
                    category=category,
                    source="overpass",
                    location=point,
                    distance_from_route_m=distance_from_route_m,
                    progress_m=progress_m,
                    priority=self.category_priority[category],
                )
            )

        return candidates

    def _build_query(self, south: float, west: float, north: float, east: float) -> str:
        bbox = f"({south},{west},{north},{east})"
        return f"""
[out:json][timeout:25];
(
  nwr["tourism"~"museum|gallery|attraction|artwork"]{bbox};
  nwr["historic"]{bbox};
  nwr["amenity"~"theatre|arts_centre"]{bbox};
  nwr["leisure"~"park|garden"]{bbox};
  nwr["tourism"="viewpoint"]{bbox};
  nwr["amenity"~"restaurant|cafe"]{bbox};
);
out center tags;
""".strip()

    def _extract_point(self, element: dict) -> GeoPoint | None:
        if "lat" in element and "lon" in element:
            return GeoPoint(lat=float(element["lat"]), lng=float(element["lon"]))

        center = element.get("center")
        if center and "lat" in center and "lon" in center:
            return GeoPoint(lat=float(center["lat"]), lng=float(center["lon"]))
        return None

    def _classify_category(self, tags: dict[str, str]) -> str | None:
        tourism = tags.get("tourism")
        amenity = tags.get("amenity")
        leisure = tags.get("leisure")

        if tourism in {"museum", "gallery", "attraction", "artwork", "viewpoint"}:
            return (
                TOUR_ROUTE_CATEGORY_CULTURE
                if tourism != "viewpoint"
                else TOUR_ROUTE_CATEGORY_PARK
            )
        if "historic" in tags:
            return TOUR_ROUTE_CATEGORY_CULTURE
        if amenity in {"theatre", "arts_centre"}:
            return TOUR_ROUTE_CATEGORY_CULTURE
        if leisure in {"park", "garden"}:
            return TOUR_ROUTE_CATEGORY_PARK
        if amenity in {"restaurant", "cafe"}:
            return TOUR_ROUTE_CATEGORY_FOOD
        return None
