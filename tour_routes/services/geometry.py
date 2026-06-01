from __future__ import annotations

from dataclasses import dataclass
from math import asin, cos, hypot, radians, sin, sqrt

from tour_routes.types import GeoPoint

EARTH_RADIUS_M = 6_371_000.0
METERS_PER_DEGREE_LAT = 111_320.0


@dataclass(frozen=True)
class RouteProjection:
    point: GeoPoint
    distance_m: float
    progress_m: float
    segment_index: int
    segment_start: GeoPoint
    segment_end: GeoPoint


def haversine_distance_m(a: GeoPoint, b: GeoPoint) -> float:
    lat1 = radians(a.lat)
    lat2 = radians(b.lat)
    d_lat = lat2 - lat1
    d_lng = radians(b.lng - a.lng)
    h = sin(d_lat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(d_lng / 2) ** 2
    return 2 * EARTH_RADIUS_M * asin(sqrt(h))


def route_cumulative_distances(points: list[GeoPoint]) -> list[float]:
    if not points:
        return []

    distances = [0.0]
    total = 0.0
    for start, end in zip(points, points[1:]):
        total += haversine_distance_m(start, end)
        distances.append(total)
    return distances


def polyline_distance_m(points: list[GeoPoint]) -> float:
    if len(points) < 2:
        return 0.0

    total = 0.0
    for start, end in zip(points, points[1:]):
        total += haversine_distance_m(start, end)
    return total


def sample_route_positions(total_distance_m: float, interval_m: float = 100.0) -> list[float]:
    if total_distance_m <= 0:
        return [0.0]

    positions: list[float] = []
    current = 0.0
    while current <= total_distance_m:
        positions.append(current)
        current += interval_m

    if positions[-1] != total_distance_m:
        positions.append(total_distance_m)
    return positions


def expand_bbox(points: list[GeoPoint], padding_m: float) -> tuple[float, float, float, float]:
    south = min(point.lat for point in points)
    north = max(point.lat for point in points)
    west = min(point.lng for point in points)
    east = max(point.lng for point in points)

    center_lat = (south + north) / 2 if points else 0.0
    padding_lat = padding_m / METERS_PER_DEGREE_LAT
    meters_per_degree_lng = max(1.0, METERS_PER_DEGREE_LAT * cos(radians(center_lat)))
    padding_lng = padding_m / meters_per_degree_lng
    return (
        south - padding_lat,
        west - padding_lng,
        north + padding_lat,
        east + padding_lng,
    )


def project_point_onto_route(point: GeoPoint, route_points: list[GeoPoint]) -> tuple[float, float]:
    projection = locate_point_on_route(point, route_points)
    return projection.distance_m, projection.progress_m


def locate_point_on_route(point: GeoPoint, route_points: list[GeoPoint]) -> RouteProjection:
    if not route_points:
        return RouteProjection(
            point=point,
            distance_m=0.0,
            progress_m=0.0,
            segment_index=0,
            segment_start=point,
            segment_end=point,
        )
    if len(route_points) == 1:
        route_point = route_points[0]
        return RouteProjection(
            point=route_point,
            distance_m=haversine_distance_m(point, route_point),
            progress_m=0.0,
            segment_index=0,
            segment_start=route_point,
            segment_end=route_point,
        )

    cumulative = route_cumulative_distances(route_points)
    reference = route_points[0]
    best_distance = float("inf")
    best_progress = 0.0
    best_projection = route_points[0]
    best_segment_index = 0
    best_segment_start = route_points[0]
    best_segment_end = route_points[1]

    for index, (start, end) in enumerate(zip(route_points, route_points[1:])):
        ref_lat = radians((start.lat + end.lat + point.lat) / 3)
        meters_per_degree_lng = max(1.0, METERS_PER_DEGREE_LAT * cos(ref_lat))

        start_x = (start.lng - reference.lng) * meters_per_degree_lng
        start_y = (start.lat - reference.lat) * METERS_PER_DEGREE_LAT
        end_x = (end.lng - reference.lng) * meters_per_degree_lng
        end_y = (end.lat - reference.lat) * METERS_PER_DEGREE_LAT
        point_x = (point.lng - reference.lng) * meters_per_degree_lng
        point_y = (point.lat - reference.lat) * METERS_PER_DEGREE_LAT

        seg_x = end_x - start_x
        seg_y = end_y - start_y
        seg_len_sq = seg_x * seg_x + seg_y * seg_y
        if seg_len_sq == 0:
            projection_factor = 0.0
        else:
            projection_factor = (
                ((point_x - start_x) * seg_x) + ((point_y - start_y) * seg_y)
            ) / seg_len_sq
            projection_factor = max(0.0, min(1.0, projection_factor))

        projected_x = start_x + projection_factor * seg_x
        projected_y = start_y + projection_factor * seg_y
        distance = hypot(point_x - projected_x, point_y - projected_y)
        segment_length = hypot(seg_x, seg_y)
        progress = cumulative[index] + (segment_length * projection_factor)
        projected_point = GeoPoint(
            lat=reference.lat + (projected_y / METERS_PER_DEGREE_LAT),
            lng=reference.lng + (projected_x / meters_per_degree_lng),
        )

        if distance < best_distance:
            best_distance = distance
            best_progress = progress
            best_projection = projected_point
            best_segment_index = index
            best_segment_start = start
            best_segment_end = end

    return RouteProjection(
        point=best_projection,
        distance_m=best_distance,
        progress_m=best_progress,
        segment_index=best_segment_index,
        segment_start=best_segment_start,
        segment_end=best_segment_end,
    )


def interpolate_route_point(route_points: list[GeoPoint], progress_m: float) -> GeoPoint:
    if not route_points:
        raise ValueError("A rota precisa ter pelo menos um ponto.")

    if len(route_points) == 1:
        return route_points[0]

    cumulative = route_cumulative_distances(route_points)
    clamped_progress = max(0.0, min(progress_m, cumulative[-1]))

    for index, (start, end) in enumerate(zip(route_points, route_points[1:])):
        segment_start_progress = cumulative[index]
        segment_end_progress = cumulative[index + 1]
        segment_distance = segment_end_progress - segment_start_progress
        if clamped_progress > segment_end_progress and index < len(route_points) - 2:
            continue

        if segment_distance <= 0:
            return start

        factor = (clamped_progress - segment_start_progress) / segment_distance
        factor = max(0.0, min(1.0, factor))
        return GeoPoint(
            lat=start.lat + ((end.lat - start.lat) * factor),
            lng=start.lng + ((end.lng - start.lng) * factor),
        )

    return route_points[-1]


def slice_route_between(
    route_points: list[GeoPoint],
    start_progress_m: float,
    end_progress_m: float,
) -> list[GeoPoint]:
    if not route_points:
        return []

    if len(route_points) == 1:
        return [route_points[0]]

    cumulative = route_cumulative_distances(route_points)
    reverse = end_progress_m < start_progress_m
    start_progress = min(start_progress_m, end_progress_m)
    end_progress = max(start_progress_m, end_progress_m)

    points = [interpolate_route_point(route_points, start_progress)]
    for index, point in enumerate(route_points[1:-1], start=1):
        point_progress = cumulative[index]
        if start_progress < point_progress < end_progress:
            points.append(point)
    points.append(interpolate_route_point(route_points, end_progress))

    if reverse:
        points.reverse()
    return _dedupe_points(points)


def _dedupe_points(points: list[GeoPoint]) -> list[GeoPoint]:
    if not points:
        return []

    deduped = [points[0]]
    for point in points[1:]:
        previous = deduped[-1]
        if previous.lat == point.lat and previous.lng == point.lng:
            continue
        deduped.append(point)
    return deduped
