from __future__ import annotations

from django.conf import settings
from django.db import models


class TourRouteCache(models.Model):
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
        verbose_name = "Cache de rota turistica"
        verbose_name_plural = "Caches de rotas turisticas"
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return f"{self.origin_query} -> {self.destination_query}"


class SavedTourRoute(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="saved_tour_routes",
    )
    cache = models.ForeignKey(
        TourRouteCache,
        on_delete=models.PROTECT,
        related_name="saved_routes",
    )
    origin_query = models.CharField(max_length=255, blank=True)
    destination_query = models.CharField(max_length=255, blank=True)
    origin_label = models.CharField(max_length=255, blank=True)
    destination_label = models.CharField(max_length=255, blank=True)
    excluded_stop_ids = models.JSONField(default=list, blank=True)
    visited_stop_ids = models.JSONField(default=list, blank=True)
    distance_m = models.PositiveIntegerField(default=0)
    duration_s = models.PositiveIntegerField(default=0)
    route_payload = models.JSONField(default=dict, blank=True)
    map_payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Rota turistica salva"
        verbose_name_plural = "Rotas turisticas salvas"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} -> {self.destination_label or self.destination_query}"


class TourRoutePoiDetail(models.Model):
    stop_id = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=255)
    category = models.CharField(max_length=32)
    lat = models.FloatField()
    lng = models.FloatField()
    source = models.CharField(max_length=32, default="overpass")
    osm_type = models.CharField(max_length=16, blank=True)
    osm_id = models.BigIntegerField(null=True, blank=True)
    wikidata_id = models.CharField(max_length=64, blank=True)
    wikipedia_title = models.CharField(max_length=255, blank=True)
    address = models.TextField(blank=True)
    summary = models.TextField(blank=True)
    image_url = models.URLField(blank=True)
    source_url = models.URLField(blank=True)
    website = models.URLField(blank=True)
    opening_hours = models.CharField(max_length=255, blank=True)
    detail_status = models.CharField(max_length=32, default="pending")
    raw_payload = models.JSONField(default=dict, blank=True)
    details_fetched_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Detalhe de ponto turistico"
        verbose_name_plural = "Detalhes de pontos turisticos"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class UserTourPlace(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tour_places",
    )
    poi_detail = models.ForeignKey(
        TourRoutePoiDetail,
        on_delete=models.CASCADE,
        related_name="user_places",
    )
    is_visited = models.BooleanField(default=False)
    visited_at = models.DateTimeField(null=True, blank=True)
    first_seen_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)
    seen_count = models.PositiveIntegerField(default=1)
    last_seen_route = models.ForeignKey(
        SavedTourRoute,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="seen_places",
    )

    class Meta:
        verbose_name = "Lugar de rota do usuario"
        verbose_name_plural = "Lugares de rota do usuario"
        ordering = ["-last_seen_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "poi_detail"],
                name="tour_routes_unique_user_poi_place",
            )
        ]
        indexes = [
            models.Index(fields=["user", "-last_seen_at"]),
            models.Index(fields=["user", "is_visited"]),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} -> {self.poi_detail.name}"
