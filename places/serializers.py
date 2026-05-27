from rest_framework import serializers

from .models import Category, Place, PlaceImage


class LocationField(serializers.Field):
    """Serializa PostGIS Point como {'lat': ..., 'lng': ...} e aceita o mesmo no input."""

    def to_representation(self, value):
        if value is None:
            return None
        return {"lat": value.y, "lng": value.x}

    def to_internal_value(self, data):
        from django.contrib.gis.geos import Point

        if not isinstance(data, dict) or "lat" not in data or "lng" not in data:
            raise serializers.ValidationError(
                "location deve ser objeto {lat, lng} em graus decimais."
            )
        try:
            lat = float(data["lat"])
            lng = float(data["lng"])
        except (TypeError, ValueError) as exc:
            raise serializers.ValidationError(
                "lat/lng devem ser numéricos."
            ) from exc
        return Point(lng, lat, srid=4326)


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id", "slug", "name", "icon_name")


class PlaceImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlaceImage
        fields = ("id", "url", "order", "caption")


class PlaceSerializer(serializers.ModelSerializer):
    """Shape consumido pelo frontend (src/services/places.ts → type Place)."""

    kind = serializers.SlugRelatedField(
        source="category", slug_field="slug", read_only=True
    )
    location = LocationField()
    images = serializers.SerializerMethodField()
    about = serializers.CharField(source="description", read_only=True)
    hours = serializers.CharField(source="hours_open", read_only=True)
    priceLabel = serializers.SerializerMethodField()
    distanceKm = serializers.SerializerMethodField()

    class Meta:
        model = Place
        fields = (
            "id",
            "slug",
            "kind",
            "name",
            "about",
            "images",
            "hours",
            "priceLabel",
            "distanceKm",
            "location",
        )

    def get_images(self, obj: Place) -> list[str]:
        return list(obj.images.order_by("order").values_list("url", flat=True))

    def get_priceLabel(self, obj: Place) -> str:
        if obj.price_cents in (None, 0):
            return "Grátis"
        return f"R$ {obj.price_cents / 100:.2f}".replace(".", ",")

    def get_distanceKm(self, obj: Place) -> float:
        # Calculado no frontend a partir da localização do usuário; default 0.
        annotated = getattr(obj, "distance_m_annotated", None)
        if annotated is not None:
            return round(annotated / 1000, 2)
        return 0.0
