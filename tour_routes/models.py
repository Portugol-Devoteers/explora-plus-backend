from __future__ import annotations

from django.conf import settings
from django.contrib.gis.db import models

from core.domain import ROUTE_MODE_TOUR, ROUTE_STOP_STATE_CHOICES, ROUTE_STOP_STATE_ACTIVE
from .constants import (
    TOUR_ROUTE_DEFAULT_INCLUDE_CULTURE,
    TOUR_ROUTE_DEFAULT_INCLUDE_FOOD,
    TOUR_ROUTE_DEFAULT_INCLUDE_PARK,
    TOUR_ROUTE_DEFAULT_MAX_SEARCH_RADIUS_M,
    TOUR_ROUTE_DEFAULT_POI_SPACING_M,
    TOUR_ROUTE_MAX_SEARCH_RADIUS_PRESETS,
    TOUR_ROUTE_POI_SPACING_PRESETS,
)


class RouteSearchCache(models.Model):
    cache_key = models.CharField(max_length=64, unique=True)
    origin_query = models.CharField(max_length=255, blank=True)
    destination_query = models.CharField(max_length=255, blank=True)
    search_payload = models.JSONField(default=dict, blank=True)
    route_payload = models.JSONField(default=dict, blank=True)
    map_payload = models.JSONField(default=dict, blank=True)
    hit_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Route search cache"
        verbose_name_plural = "Route search caches"
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return f"{self.origin_query} -> {self.destination_query}"


class UserRouteSearchPreference(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="route_search_preferences",
    )
    include_culture = models.BooleanField(default=TOUR_ROUTE_DEFAULT_INCLUDE_CULTURE)
    include_park = models.BooleanField(default=TOUR_ROUTE_DEFAULT_INCLUDE_PARK)
    include_food = models.BooleanField(default=TOUR_ROUTE_DEFAULT_INCLUDE_FOOD)
    poi_spacing_m = models.PositiveSmallIntegerField(
        default=TOUR_ROUTE_DEFAULT_POI_SPACING_M,
        choices=[(value, f"{value} m") for value in TOUR_ROUTE_POI_SPACING_PRESETS],
    )
    max_search_radius_m = models.PositiveSmallIntegerField(
        default=TOUR_ROUTE_DEFAULT_MAX_SEARCH_RADIUS_M,
        choices=[(value, f"{value} m") for value in TOUR_ROUTE_MAX_SEARCH_RADIUS_PRESETS],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "User route search preference"
        verbose_name_plural = "User route search preferences"

    def __str__(self) -> str:
        return f"{self.user_id} route search preferences"


class TourRoute(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tour_routes",
    )
    search_cache = models.ForeignKey(
        RouteSearchCache,
        on_delete=models.PROTECT,
        related_name="routes",
    )
    origin_query = models.CharField(max_length=255, blank=True)
    destination_query = models.CharField(max_length=255, blank=True)
    origin_label = models.CharField(max_length=255, blank=True)
    destination_label = models.CharField(max_length=255, blank=True)
    origin_location = models.PointField(geography=True, srid=4326)
    destination_location = models.PointField(geography=True, srid=4326)
    mode = models.CharField(max_length=32, default=ROUTE_MODE_TOUR)
    distance_m = models.PositiveIntegerField(default=0)
    duration_s = models.PositiveIntegerField(default=0)
    direct_distance_m = models.PositiveIntegerField(default=0)
    direct_duration_s = models.PositiveIntegerField(default=0)
    route_geometry = models.LineStringField(geography=True, srid=4326, null=True, blank=True)
    direct_route_geometry = models.LineStringField(
        geography=True,
        srid=4326,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Tour route"
        verbose_name_plural = "Tour routes"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} -> {self.destination_label or self.destination_query}"


class TourRouteStop(models.Model):
    route = models.ForeignKey(
        TourRoute,
        on_delete=models.CASCADE,
        related_name="stops",
    )
    place = models.ForeignKey(
        "places.Place",
        on_delete=models.CASCADE,
        related_name="route_stops",
    )
    display_order = models.PositiveIntegerField()
    waypoint_order = models.PositiveIntegerField(null=True, blank=True)
    state = models.CharField(
        max_length=16,
        choices=ROUTE_STOP_STATE_CHOICES,
        default=ROUTE_STOP_STATE_ACTIVE,
    )
    source = models.CharField(max_length=32, blank=True)
    distance_from_route_m = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Tour route stop"
        verbose_name_plural = "Tour route stops"
        ordering = ["display_order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["route", "place"],
                name="tour_routes_unique_route_place",
            ),
            models.UniqueConstraint(
                fields=["route", "display_order"],
                name="tour_routes_unique_route_display_order",
            ),
        ]
        indexes = [
            models.Index(fields=["route", "state"]),
            models.Index(fields=["route", "waypoint_order"]),
        ]

    def __str__(self) -> str:
        return f"{self.route_id} #{self.display_order} -> {self.place.name}"
