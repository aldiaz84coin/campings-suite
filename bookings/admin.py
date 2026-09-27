from django.contrib import admin

from .models import BookingRequest


@admin.register(BookingRequest)
class BookingRequestAdmin(admin.ModelAdmin):
    list_display = (
        "reference",
        "camping",
        "name",
        "arrival",
        "departure",
        "accommodation_name",
        "status",
        "created_at",
    )
    list_filter = ("status", "camping")
    search_fields = ("reference", "name", "email", "camping__name")
    date_hierarchy = "arrival"
    readonly_fields = ("reference", "token", "quote", "estimated_total", "created_at", "updated_at")
    autocomplete_fields = ("camping",)
    raw_id_fields = ("accommodation",)
    filter_horizontal = ("extras",)
