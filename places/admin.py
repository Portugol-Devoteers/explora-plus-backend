from django.contrib.gis import admin as gis_admin

from .models import Category, Place, PlaceImage


class PlaceImageInline(gis_admin.TabularInline):
    model = PlaceImage
    extra = 1
    fields = ("url", "order", "caption")


@gis_admin.register(Category)
class CategoryAdmin(gis_admin.ModelAdmin):
    list_display = ("name", "slug", "icon_name")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name", "slug")


@gis_admin.register(Place)
class PlaceAdmin(gis_admin.GISModelAdmin):
    list_display = (
        "name",
        "category",
        "is_active",
        "price_cents",
        "event_start_at",
        "updated_at",
    )
    list_filter = ("category", "is_active")
    search_fields = ("name", "slug", "address")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [PlaceImageInline]
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (None, {"fields": ("name", "slug", "category", "is_active")}),
        ("Conteúdo", {"fields": ("description", "address", "hours_open")}),
        ("Localização", {"fields": ("location",)}),
        ("Preço", {"fields": ("price_cents", "currency")}),
        ("Evento (opcional)", {"fields": ("event_start_at", "event_end_at")}),
        ("Auditoria", {"fields": ("created_at", "updated_at")}),
    )


@gis_admin.register(PlaceImage)
class PlaceImageAdmin(gis_admin.ModelAdmin):
    list_display = ("place", "order", "caption", "url")
    list_filter = ("place",)
