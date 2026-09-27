import json

from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.db.models import Max
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from campings.models import Photo
from core.images import ImageProcessingError, process_photo

from ..forms import PhotoForm, PhotoUploadForm
from ..utils import camping_view, panel_render, wants_json


def _save_photo(camping, upload, position):
    large, thumb = process_photo(upload)
    photo = Photo(camping=camping, position=position, width=large.width, height=large.height)
    photo.image.save(large.file.name, large.file, save=False)
    photo.thumbnail.save(thumb.file.name.replace(".webp", "-thumb.webp"), thumb.file, save=False)
    photo.save()
    return photo


@camping_view()
def photos(request, camping):
    form = PhotoUploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST":
        if not form.is_valid():
            if wants_json(request):
                return JsonResponse({"ok": False, "errors": [_("Choose at least one image.")]}, status=400)
        else:
            created, errors = [], []
            current = camping.photos.count()
            next_position = (camping.photos.aggregate(top=Max("position"))["top"] or 0) + 1
            for upload in form.cleaned_data["images"]:
                if current + len(created) >= settings.MAX_PHOTOS_PER_CAMPING:
                    errors.append(
                        _("You have reached the limit of %(max)s photos.") % {"max": settings.MAX_PHOTOS_PER_CAMPING}
                    )
                    break
                try:
                    created.append(_save_photo(camping, upload, next_position + len(created)))
                except ImageProcessingError as error:
                    errors.append(f"{upload.name}: {error}")
            if wants_json(request):
                return JsonResponse(
                    {
                        "ok": not errors,
                        "errors": errors,
                        "photos": [{"id": p.pk, "thumbnail": p.thumbnail.url} for p in created],
                    },
                    status=200 if created or not errors else 400,
                )
            for error in errors:
                messages.error(request, error)
            if created:
                messages.success(request, _("%(count)s photo(s) uploaded.") % {"count": len(created)})
            return redirect("panel:photos", slug=camping.slug)

    context = {
        "form": form,
        "photos": camping.photos.select_related("accommodation"),
        "max_photos": settings.MAX_PHOTOS_PER_CAMPING,
        "max_upload_mb": settings.MAX_UPLOAD_MB,
    }
    return panel_render(request, "panel/photos.html", context, section="photos")


@camping_view()
def photo_edit(request, camping, pk):
    photo = get_object_or_404(Photo, pk=pk, camping=camping)
    form = PhotoForm(request.POST or None, instance=photo, camping=camping)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("The photo has been saved."))
        return redirect("panel:photos", slug=camping.slug)
    return panel_render(request, "panel/photo_form.html", {"form": form, "photo": photo}, section="photos")


@require_POST
@camping_view()
def photo_delete(request, camping, pk):
    photo = get_object_or_404(Photo, pk=pk, camping=camping)
    photo.delete()
    if wants_json(request):
        return JsonResponse({"ok": True})
    messages.success(request, _("The photo has been deleted."))
    return redirect("panel:photos", slug=camping.slug)


def _apply_order(camping, ordered_ids):
    photos = {p.pk: p for p in camping.photos.all()}
    ordered = [photos[pk] for pk in ordered_ids if pk in photos]
    ordered += [p for pk, p in sorted(photos.items(), key=lambda item: (item[1].position, item[0])) if p not in ordered]
    with transaction.atomic():
        for position, photo in enumerate(ordered):
            if photo.position != position:
                photo.position = position
                photo.save(update_fields=["position"])


@require_POST
@camping_view()
def photo_reorder(request, camping):
    try:
        payload = json.loads(request.body or b"{}")
        ordered_ids = [int(pk) for pk in payload.get("order", [])]
    except (ValueError, TypeError, AttributeError):
        return HttpResponseBadRequest("Invalid order")
    _apply_order(camping, ordered_ids)
    return JsonResponse({"ok": True})


@require_POST
@camping_view()
def photo_cover(request, camping, pk):
    photo = get_object_or_404(Photo, pk=pk, camping=camping)
    _apply_order(camping, [photo.pk])
    messages.success(request, _("This photo is now the main photo of your page."))
    return redirect("panel:photos", slug=camping.slug)


@require_POST
@camping_view()
def photo_move(request, camping, pk, direction):
    """Move a photo one position up or down (fallback without JavaScript)."""
    ids = list(camping.photos.values_list("pk", flat=True))
    if pk not in ids:
        return redirect("panel:photos", slug=camping.slug)
    index = ids.index(pk)
    target = index - 1 if direction == "up" else index + 1
    if 0 <= target < len(ids):
        ids[index], ids[target] = ids[target], ids[index]
        _apply_order(camping, ids)
    return redirect("panel:photos", slug=camping.slug)
