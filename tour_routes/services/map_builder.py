from __future__ import annotations

from tour_routes.types import TourRouteResult


class GeoJsonMapBuilder:
    def build(self, result: TourRouteResult) -> dict:
        features = [
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [
                        [point.lng, point.lat] for point in result.route_path.coordinates
                    ],
                },
                "properties": {
                    "kind": "route",
                    "distance_m": result.route_path.distance_m,
                    "duration_s": result.route_path.duration_s,
                },
            },
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [
                        result.origin.location.lng,
                        result.origin.location.lat,
                    ],
                },
                "properties": {
                    "kind": "origin",
                    "label": result.origin.label,
                },
            },
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [
                        result.destination.location.lng,
                        result.destination.location.lat,
                    ],
                },
                "properties": {
                    "kind": "destination",
                    "label": result.destination.label,
                },
            },
        ]

        for index, poi in enumerate(result.places_to_pass, start=1):
            features.append(
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [poi.location.lng, poi.location.lat],
                    },
                    "properties": {
                        "kind": "poi",
                        "order": index,
                        "name": poi.name,
                        "category": poi.category,
                        "source": poi.source,
                        "distance_from_route_m": int(round(poi.distance_from_route_m)),
                    },
                }
            )

        return {
            "type": "FeatureCollection",
            "features": features,
        }
