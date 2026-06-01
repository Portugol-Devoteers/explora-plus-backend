from django.contrib import admin

from .models import SavedTourRoute, TourRouteCache


@admin.register(TourRouteCache)
class TourRouteCacheAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "origin_query",
        "destination_query",
        "hit_count",
        "updated_at",
    )
    search_fields = ("origin_query", "destination_query", "cache_key")
    readonly_fields = ("created_at", "updated_at")


@admin.register(SavedTourRoute)
class SavedTourRouteAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "destination_label",
        "distance_m",
        "duration_s",
        "created_at",
    )
    search_fields = (
        "user__username",
        "origin_query",
        "destination_query",
        "origin_label",
        "destination_label",
    )
    readonly_fields = ("created_at", "updated_at")
