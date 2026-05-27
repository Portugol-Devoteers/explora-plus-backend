from django.contrib import admin

from .models import Ticket


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "user",
        "place",
        "quantity",
        "total_cents",
        "status",
        "purchased_at",
        "used_at",
    )
    list_filter = ("status", "purchased_at")
    search_fields = ("code", "user__username", "place__name")
    readonly_fields = ("code", "purchased_at")
