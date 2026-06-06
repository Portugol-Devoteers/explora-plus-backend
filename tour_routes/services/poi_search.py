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

class OverpassPoiSearcher:
    endpoint = "https://overpass-api.de/api/interpreter"
    category_priority = TOUR_ROUTE_CATEGORY_PRIORITY

    def __init__(self, client: JsonHttpClient | None = None):
        self.client = client or JsonHttpClient()

    def search(
        self,
        route_path: RoutePath,
        *,
        enabled_categories: tuple[str, ...],
        max_distance_from_route_m: int,
    ) -> list[PoiCandidate]:
        if not route_path.coordinates:
            return []
        if not enabled_categories:
            return []

        bbox = expand_bbox(route_path.coordinates, padding_m=float(max_distance_from_route_m))
        query = self._build_query(*bbox, enabled_categories=enabled_categories)

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
            if distance_from_route_m > float(max_distance_from_route_m):
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
                    osm_type=str(element.get("type")) if element.get("type") else None,
                    osm_id=int(element["id"]) if element.get("id") is not None else None,
                    wikidata_id=tags.get("wikidata"),
                    wikipedia_title=self._normalize_wikipedia_title(tags.get("wikipedia")),
                    website=tags.get("website") or tags.get("contact:website"),
                    opening_hours=tags.get("opening_hours"),
                    address=self._build_address(tags),
                    raw_tags={
                        key: str(value)
                        for key, value in tags.items()
                        if isinstance(value, (str, int, float))
                    },
                )
            )

        return candidates

    def _build_query(
        self,
        south: float,
        west: float,
        north: float,
        east: float,
        *,
        enabled_categories: tuple[str, ...],
    ) -> str:
        bbox = f"({south},{west},{north},{east})"
        clauses: list[str] = []
        if TOUR_ROUTE_CATEGORY_CULTURE in enabled_categories:
            clauses.extend(
                [
                    f'nwr["tourism"~"museum|gallery|attraction|artwork"]{bbox};',
                    f'nwr["historic"]{bbox};',
                    f'nwr["amenity"~"theatre|arts_centre"]{bbox};',
                ]
            )
        if TOUR_ROUTE_CATEGORY_PARK in enabled_categories:
            clauses.extend(
                [
                    f'nwr["leisure"~"park|garden"]{bbox};',
                    f'nwr["tourism"="viewpoint"]{bbox};',
                ]
            )
        if TOUR_ROUTE_CATEGORY_FOOD in enabled_categories:
            clauses.append(f'nwr["amenity"~"restaurant|cafe"]{bbox};')

        query_body = "\n  ".join(clauses)
        return f"""
[out:json][timeout:25];
(
  {query_body}
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

    def _normalize_wikipedia_title(self, wikipedia_tag: str | None) -> str | None:
        if not wikipedia_tag:
            return None
        normalized = wikipedia_tag.strip()
        return normalized or None

    def _build_address(self, tags: dict[str, str]) -> str | None:
        street = tags.get("addr:street")
        number = tags.get("addr:housenumber")
        suburb = tags.get("addr:suburb")
        city = tags.get("addr:city")
        parts = []
        if street:
            street_part = street
            if number:
                street_part = f"{street_part}, {number}"
            parts.append(street_part)
        if suburb:
            parts.append(suburb)
        if city:
            parts.append(city)
        if not parts:
            return None
        return ", ".join(parts)
