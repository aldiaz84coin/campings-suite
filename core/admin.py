from django.contrib import admin
from django.template.defaultfilters import filesizeformat

from .models import StoredFile


@admin.register(StoredFile)
class StoredFileAdmin(admin.ModelAdmin):
    list_display = ("name", "content_type", "human_size", "created_at")
    search_fields = ("name",)
    readonly_fields = ("name", "content_type", "size", "created_at")
    exclude = ("content",)

    @admin.display(description="size", ordering="size")
    def human_size(self, obj):
        return filesizeformat(obj.size)

    def has_add_permission(self, request):
        return False
