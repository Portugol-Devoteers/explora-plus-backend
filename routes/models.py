from django.conf import settings
from django.contrib.gis.db import models


class TransportMode(models.TextChoices):
    TRANSIT = "transit", "Transporte público"
    RIDESHARE = "rideshare", "Aplicativo de carro"
    WALKING = "walking", "A pé"
    DRIVING = "driving", "Carro próprio"


class Route(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="routes",
    )
    destination_place = models.ForeignKey(
        "places.Place",
        on_delete=models.PROTECT,
        related_name="routes_to",
    )
    origin = models.PointField(geography=True, srid=4326)
    transport_mode = models.CharField(
        max_length=16,
        choices=TransportMode.choices,
        default=TransportMode.WALKING,
    )
    distance_m = models.PositiveIntegerField()
    duration_s = models.PositiveIntegerField()
    polyline = models.TextField(
        help_text="Encoded polyline ou JSON LineString devolvido pelo provedor",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Rota"
        verbose_name_plural = "Rotas"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} → {self.destination_place_id} ({self.transport_mode})"
