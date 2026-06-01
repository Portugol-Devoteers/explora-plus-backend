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
