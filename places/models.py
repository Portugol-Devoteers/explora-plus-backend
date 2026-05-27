from django.contrib.gis.db import models


class Category(models.Model):
    slug = models.SlugField(max_length=64, unique=True)
    name = models.CharField(max_length=120)
    icon_name = models.CharField(max_length=64, blank=True)

    class Meta:
        verbose_name = "Categoria"
        verbose_name_plural = "Categorias"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Place(models.Model):
    slug = models.SlugField(max_length=160, unique=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="places",
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    location = models.PointField(geography=True, srid=4326)
    address = models.CharField(max_length=255, blank=True)
    hours_open = models.CharField(max_length=120, blank=True)
    price_cents = models.PositiveIntegerField(null=True, blank=True)
    currency = models.CharField(max_length=3, default="BRL")
    event_start_at = models.DateTimeField(null=True, blank=True)
    event_end_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Lugar"
        verbose_name_plural = "Lugares"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["category", "is_active"]),
        ]

    def __str__(self) -> str:
        return self.name

    @property
    def is_event(self) -> bool:
        return self.event_start_at is not None

    @property
    def is_free(self) -> bool:
        return self.price_cents in (None, 0)


class PlaceImage(models.Model):
    place = models.ForeignKey(
        Place,
        on_delete=models.CASCADE,
        related_name="images",
    )
    url = models.URLField(max_length=500)
    order = models.PositiveSmallIntegerField(default=0)
    caption = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name = "Imagem do lugar"
        verbose_name_plural = "Imagens dos lugares"
        ordering = ["place", "order"]

    def __str__(self) -> str:
        return f"{self.place.name} #{self.order}"
