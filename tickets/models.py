import secrets
import string

from django.conf import settings
from django.db import models


class TicketStatus(models.TextChoices):
    VALID = "valid", "Válido"
    USED = "used", "Utilizado"
    EXPIRED = "expired", "Expirado"


def _generate_ticket_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    number = "".join(secrets.choice(string.digits) for _ in range(4))
    suffix = "".join(secrets.choice(alphabet) for _ in range(3))
    return f"EXP-{number}-{suffix}"


class Ticket(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tickets",
    )
    place = models.ForeignKey(
        "places.Place",
        on_delete=models.PROTECT,
        related_name="tickets",
    )
    code = models.CharField(max_length=32, unique=True, default=_generate_ticket_code)
    quantity = models.PositiveSmallIntegerField(default=1)
    total_cents = models.PositiveIntegerField()
    currency = models.CharField(max_length=3, default="BRL")
    status = models.CharField(
        max_length=16,
        choices=TicketStatus.choices,
        default=TicketStatus.VALID,
    )
    purchased_at = models.DateTimeField(auto_now_add=True)
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Ingresso"
        verbose_name_plural = "Ingressos"
        ordering = ["-purchased_at"]
        indexes = [
            models.Index(fields=["user", "-purchased_at"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self) -> str:
        return self.code

    @property
    def is_valid(self) -> bool:
        return self.status == TicketStatus.VALID
