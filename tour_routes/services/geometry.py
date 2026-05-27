from __future__ import annotations

from math import asin, cos, hypot, radians, sin, sqrt

from tour_routes.types import GeoPoint

EARTH_RADIUS_M = 6_371_000.0
METERS_PER_DEGREE_LAT = 111_320.0


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
    if not route_points:
        return 0.0, 0.0
    if len(route_points) == 1:
        return haversine_distance_m(point, route_points[0]), 0.0

    cumulative = route_cumulative_distances(route_points)
    reference = route_points[0]
    best_distance = float("inf")
    best_progress = 0.0

    for index, (start, end) in enumerate(zip(route_points, route_points[1:])):
        ref_lat = radians((start.lat + end.lat + point.lat) / 3)
        meters_per_degree_lng = METERS_PER_DEGREE_LAT * cos(ref_lat)

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

        if distance < best_distance:
            best_distance = distance
            best_progress = progress

    return best_distance, best_progress
