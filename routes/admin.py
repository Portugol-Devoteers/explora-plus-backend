from django.contrib.gis import admin as gis_admin

from .models import Route


@gis_admin.register(Route)
class RouteAdmin(gis_admin.GISModelAdmin):
    list_display = (
        "id",
        "user",
        "destination_place",
        "transport_mode",
        "distance_m",
        "duration_s",
        "created_at",
    )
    list_filter = ("transport_mode", "created_at")
    search_fields = ("user__username", "destination_place__name")
    readonly_fields = ("created_at",)
