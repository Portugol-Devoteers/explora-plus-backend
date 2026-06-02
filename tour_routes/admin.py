from django.contrib import admin

from .models import RouteSearchCache, TourRoute, TourRouteStop


class TourRouteStopInline(admin.TabularInline):
    model = TourRouteStop
    extra = 0
    fields = (
        "place",
        "display_order",
        "waypoint_order",
        "state",
        "source",
        "distance_from_route_m",
    )
    readonly_fields = ("created_at", "updated_at")


@admin.register(RouteSearchCache)
class RouteSearchCacheAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "origin_query",
        "destination_query",
        "hit_count",
        "updated_at",
    )
    search_fields = ("origin_query", "destination_query", "cache_key")
    readonly_fields = ("created_at", "updated_at")


@admin.register(TourRoute)
class TourRouteAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "destination_label",
        "mode",
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
    inlines = [TourRouteStopInline]


@admin.register(TourRouteStop)
class TourRouteStopAdmin(admin.ModelAdmin):
    list_display = (
        "route",
        "place",
        "display_order",
        "waypoint_order",
        "state",
        "distance_from_route_m",
    )
    list_filter = ("state", "source")
    search_fields = (
        "route__user__username",
        "place__name",
        "place__source_ref",
    )
    readonly_fields = ("created_at", "updated_at")
