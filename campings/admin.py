from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from core.i18n import translate_value

from .models import (
    AccommodationRate,
    AccommodationType,
    BookingPolicy,
    Camping,
    Facility,
    Membership,
    Photo,
    Season,
    SeasonPeriod,
    Service,
    ServiceRate,
)


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 0
    autocomplete_fields = ("user",)


class BookingPolicyInline(admin.StackedInline):
    model = BookingPolicy
    can_delete = False
    extra = 0


@admin.register(Camping)
class CampingAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "city",
        "region",
        "is_published",
        "is_approved",
        "custom_domain",
        "created_at",
        "public_link",
    )
    list_filter = ("is_published", "is_approved", "region")
    list_editable = ("is_approved",)
    search_fields = ("name", "slug", "city", "region", "email", "custom_domain", "legal_name", "tax_id")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("domain_verified_at",)
    inlines = [MembershipInline, BookingPolicyInline]
    actions = ["approve", "suspend"]

    @admin.display(description=_("public page"))
    def public_link(self, obj):
        return format_html('<a href="{}" target="_blank" rel="noopener">{}</a>', obj.get_absolute_url(), _("View"))

    @admin.action(description=_("Approve selected campings"))
    def approve(self, request, queryset):
        queryset.update(is_approved=True)

    @admin.action(description=_("Suspend selected campings"))
    def suspend(self, request, queryset):
        queryset.update(is_approved=False)


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "camping", "role", "created_at")
    list_filter = ("role",)
    search_fields = ("user__email", "camping__name")
    autocomplete_fields = ("user", "camping")


class TranslatedNameMixin:
    @admin.display(description=_("name"))
    def translated_name(self, obj):
        return translate_value(obj.name)


class AccommodationRateInline(admin.TabularInline):
    model = AccommodationRate
    extra = 0


@admin.register(AccommodationType)
class AccommodationTypeAdmin(TranslatedNameMixin, admin.ModelAdmin):
    list_display = ("translated_name", "camping", "kind", "base_price", "units", "is_active")
    list_filter = ("kind", "is_active")
    search_fields = ("camping__name",)
    autocomplete_fields = ("camping",)
    inlines = [AccommodationRateInline]


class ServiceRateInline(admin.TabularInline):
    model = ServiceRate
    extra = 0


@admin.register(Service)
class ServiceAdmin(TranslatedNameMixin, admin.ModelAdmin):
    list_display = ("translated_name", "camping", "price", "unit", "mode", "is_active")
    list_filter = ("mode", "unit")
    search_fields = ("camping__name",)
    autocomplete_fields = ("camping",)
    inlines = [ServiceRateInline]


class SeasonPeriodInline(admin.TabularInline):
    model = SeasonPeriod
    extra = 1


@admin.register(Season)
class SeasonAdmin(TranslatedNameMixin, admin.ModelAdmin):
    list_display = ("translated_name", "camping", "kind", "period_list", "min_nights")
    list_filter = ("kind",)
    search_fields = ("camping__name",)
    autocomplete_fields = ("camping",)
    inlines = [SeasonPeriodInline]

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("periods")

    @admin.display(description=_("periods"))
    def period_list(self, obj):
        return ", ".join(str(period) for period in obj.periods.all())


@admin.register(Facility)
class FacilityAdmin(admin.ModelAdmin):
    list_display = ("__str__", "camping", "kind", "is_paid")
    list_filter = ("kind",)
    search_fields = ("camping__name",)
    autocomplete_fields = ("camping",)


@admin.register(Photo)
class PhotoAdmin(admin.ModelAdmin):
    list_display = ("preview", "camping", "position", "created_at")
    search_fields = ("camping__name",)
    autocomplete_fields = ("camping",)
    readonly_fields = ("preview", "width", "height")

    @admin.display(description=_("preview"))
    def preview(self, obj):
        if not obj.thumbnail:
            return "-"
        return format_html('<img src="{}" style="height:60px;border-radius:4px" alt="">', obj.thumbnail.url)


@admin.register(BookingPolicy)
class BookingPolicyAdmin(admin.ModelAdmin):
    list_display = ("camping", "min_nights", "deposit_percent", "refundable", "pets_allowed")
    search_fields = ("camping__name",)
    autocomplete_fields = ("camping",)
