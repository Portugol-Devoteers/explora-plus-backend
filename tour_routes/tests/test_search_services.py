from django.test import SimpleTestCase

from tour_routes.constants import (
    TOUR_ROUTE_CATEGORY_CULTURE,
    TOUR_ROUTE_CATEGORY_PARK,
)
from tour_routes.services.poi_search import OverpassPoiSearcher
from tour_routes.services.poi_selector import PoiSelector
from tour_routes.types import GeoPoint, PoiCandidate


class OverpassPoiSearcherTests(SimpleTestCase):
    def test_build_query_only_includes_enabled_categories(self):
        searcher = OverpassPoiSearcher()

        query = searcher._build_query(0.0, 0.0, 1.0, 1.0, enabled_categories=(TOUR_ROUTE_CATEGORY_PARK,))

        self.assertIn('nwr["leisure"~"park|garden"]', query)
        self.assertIn('nwr["tourism"="viewpoint"]', query)
        self.assertNotIn('nwr["tourism"~"museum|gallery|attraction|artwork"]', query)
        self.assertNotIn('nwr["amenity"~"restaurant|cafe"]', query)


class PoiSelectorTests(SimpleTestCase):
    def setUp(self):
        self.selector = PoiSelector()
        self.candidates = [
            self._candidate("Ponto 1", 10.0),
            self._candidate("Ponto 2", 90.0),
            self._candidate("Ponto 3", 170.0),
            self._candidate("Ponto 4", 250.0),
        ]

    def test_smaller_spacing_can_select_more_stops(self):
        dense = self.selector.select(self.candidates, 250, poi_spacing_m=75)
        sparse = self.selector.select(self.candidates, 250, poi_spacing_m=150)

        self.assertGreaterEqual(len(dense), len(sparse))

    def _candidate(self, name: str, progress_m: float) -> PoiCandidate:
        return PoiCandidate(
            name=name,
            category=TOUR_ROUTE_CATEGORY_CULTURE,
            source="overpass",
            location=GeoPoint(lat=-23.56 + (progress_m / 100000.0), lng=-46.65),
            distance_from_route_m=10.0,
            progress_m=progress_m,
            priority=1,
            raw_tags={"name": name},
        )
