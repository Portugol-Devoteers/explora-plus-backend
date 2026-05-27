from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GeoPoint:
    lat: float
    lng: float

    def as_dict(self) -> dict[str, float]:
        return {"lat": self.lat, "lng": self.lng}


@dataclass(frozen=True)
class ResolvedPoint:
    label: str
    location: GeoPoint


@dataclass(frozen=True)
class RoutePath:
    distance_m: int
    duration_s: int
    coordinates: list[GeoPoint]


@dataclass(frozen=True)
class PoiCandidate:
    name: str
    category: str
    source: str
    location: GeoPoint
    distance_from_route_m: float
    progress_m: float
    priority: int


@dataclass(frozen=True)
class TourRouteResult:
    origin: ResolvedPoint
    destination: ResolvedPoint
    route_path: RoutePath
    places_to_pass: list[PoiCandidate]
