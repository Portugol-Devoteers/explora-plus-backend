from __future__ import annotations

from rest_framework import serializers

from .types import GeoPoint, TourRouteResult


class CoordinateSerializer(serializers.Serializer):
    lat = serializers.FloatField()
    lng = serializers.FloatField()


class RouteEndpointSerializer(serializers.Serializer):
    address = serializers.CharField(required=False, allow_blank=False)
    location = CoordinateSerializer(required=False)

    def validate(self, attrs):
        has_address = bool(attrs.get("address"))
        has_location = attrs.get("location") is not None

        if has_address == has_location:
            raise serializers.ValidationError(
                "Informe exatamente um entre 'address' e 'location'."
            )
        return attrs


class TourRouteRequestSerializer(serializers.Serializer):
    origin = RouteEndpointSerializer()
    destination = RouteEndpointSerializer()


class ResolvedPointSerializer(serializers.Serializer):
    label = serializers.CharField()
    location = CoordinateSerializer()


class PlaceToPassSerializer(serializers.Serializer):
    order = serializers.IntegerField()
    name = serializers.CharField()
    category = serializers.CharField()
    location = CoordinateSerializer()
    distance_from_route_m = serializers.IntegerField()
    source = serializers.CharField()


class RoutePayloadSerializer(serializers.Serializer):
    origin = ResolvedPointSerializer()
    destination = ResolvedPointSerializer()
    distance_m = serializers.IntegerField()
    duration_s = serializers.IntegerField()
    polyline_points = CoordinateSerializer(many=True)
    places_to_pass = PlaceToPassSerializer(many=True)


class TourRouteResponseSerializer(serializers.Serializer):
    route = RoutePayloadSerializer()
    map = serializers.JSONField()


def serialize_result(result: TourRouteResult, map_payload: dict) -> dict:
    payload = {
        "route": {
            "origin": {
                "label": result.origin.label,
                "location": result.origin.location.as_dict(),
            },
            "destination": {
                "label": result.destination.label,
                "location": result.destination.location.as_dict(),
            },
            "distance_m": result.route_path.distance_m,
            "duration_s": result.route_path.duration_s,
            "polyline_points": [
                point.as_dict() for point in result.route_path.coordinates
            ],
            "places_to_pass": [
                {
                    "order": index,
                    "name": poi.name,
                    "category": poi.category,
                    "location": poi.location.as_dict(),
                    "distance_from_route_m": int(round(poi.distance_from_route_m)),
                    "source": poi.source,
                }
                for index, poi in enumerate(result.places_to_pass, start=1)
            ],
        },
        "map": map_payload,
    }
    return TourRouteResponseSerializer(instance=payload).data
