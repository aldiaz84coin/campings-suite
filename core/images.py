"""Image normalisation for uploads: fix orientation, resize and convert to WebP."""

import uuid
from dataclasses import dataclass
from io import BytesIO

from django.conf import settings
from django.core.files.base import ContentFile
from django.utils.translation import gettext as _
from PIL import Image, ImageOps, UnidentifiedImageError

try:  # iPhone photos (HEIC/HEIF)
    import pillow_heif

    pillow_heif.register_heif_opener()
except ImportError:  # pragma: no cover - optional dependency
    pass

# Refuse absurdly large images before decoding them (~ 80 megapixels).
Image.MAX_IMAGE_PIXELS = 80_000_000


class ImageProcessingError(Exception):
    pass


@dataclass
class ProcessedImage:
    file: ContentFile
    width: int
    height: int


def max_upload_bytes():
    return settings.MAX_UPLOAD_MB * 1024 * 1024


def open_image(uploaded):
    size = getattr(uploaded, "size", None)
    if size and size > max_upload_bytes():
        raise ImageProcessingError(_("The file is too large (maximum %(mb)s MB).") % {"mb": settings.MAX_UPLOAD_MB})
    try:
        if hasattr(uploaded, "seek"):
            uploaded.seek(0)
        image = Image.open(uploaded)
        image.load()
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError, SyntaxError) as exc:
        raise ImageProcessingError(_("The file is not a valid image.")) from exc
    try:
        image = ImageOps.exif_transpose(image)
    except Exception:  # noqa: BLE001 - broken EXIF data should not block uploads
        pass
    return image


def _has_alpha(image):
    return image.mode in ("RGBA", "LA", "PA") or (image.mode == "P" and "transparency" in image.info)


def render_webp(image, max_side, quality=82, keep_alpha=False):
    """Return a resized WebP copy of ``image`` whose longest side is ``max_side``."""
    variant = image.copy()
    variant.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    if keep_alpha and _has_alpha(variant):
        variant = variant.convert("RGBA")
    else:
        if _has_alpha(variant):
            background = Image.new("RGB", variant.size, (255, 255, 255))
            rgba = variant.convert("RGBA")
            background.paste(rgba, mask=rgba.getchannel("A"))
            variant = background
        elif variant.mode != "RGB":
            variant = variant.convert("RGB")
    buffer = BytesIO()
    variant.save(buffer, "WEBP", quality=quality, method=4)
    name = f"{uuid.uuid4().hex}.webp"
    return ProcessedImage(ContentFile(buffer.getvalue(), name=name), variant.width, variant.height)


def process_photo(uploaded):
    """Large (for galleries) and small (for cards) versions of a photo."""
    image = open_image(uploaded)
    large = render_webp(image, 2000, quality=80)
    thumb = render_webp(image, 800, quality=78)
    return large, thumb


def process_logo(uploaded):
    image = open_image(uploaded)
    return render_webp(image, 600, quality=90, keep_alpha=True)
