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
class RoutePoi:
    name: str
    category: str
    source: str
    location: GeoPoint
    distance_from_route_m: float
    progress_m: float
    priority: int
    included_in_route: bool
    waypoint_order: int | None


@dataclass(frozen=True)
class TourRouteResult:
    origin: ResolvedPoint
    destination: ResolvedPoint
    route_path: RoutePath
    direct_route_path: RoutePath
    tour_route_path: RoutePath | None
    mode: str
    places_to_pass: list[RoutePoi]
