from django.core.files.base import ContentFile
from django.test import TestCase, override_settings

from core.models import StoredFile
from core.storage import DatabaseStorage


class DatabaseStorageTests(TestCase):
    def test_save_open_delete(self):
        storage = DatabaseStorage()
        name = storage.save("campings/1/photos/a.webp", ContentFile(b"RIFFdata", name="a.webp"))
        self.assertEqual(name, "campings/1/photos/a.webp")
        self.assertTrue(storage.exists(name))
        self.assertEqual(storage.size(name), 8)
        self.assertEqual(storage.open(name).read(), b"RIFFdata")
        self.assertEqual(storage.url(name), "/media/campings/1/photos/a.webp")
        self.assertEqual(StoredFile.objects.get().content_type, "image/webp")
        # A second file with the same name gets a different one.
        other = storage.save("campings/1/photos/a.webp", ContentFile(b"x", name="a.webp"))
        self.assertNotEqual(other, name)
        storage.delete(name)
        self.assertFalse(storage.exists(name))

    @override_settings(MEDIA_STORAGE="db")
    def test_media_view_serves_with_cache_headers(self):
        from core.views import media

        storage = DatabaseStorage()
        name = storage.save("x/y.webp", ContentFile(b"abc", name="y.webp"))
        from django.test import RequestFactory

        request = RequestFactory().get(f"/media/{name}")
        response = media(request, name)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"abc")
        self.assertIn("immutable", response["Cache-Control"])
        request = RequestFactory().get(f"/media/{name}", HTTP_IF_NONE_MATCH=response["ETag"])
        self.assertEqual(media(request, name).status_code, 304)
