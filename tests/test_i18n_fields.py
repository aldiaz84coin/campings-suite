from django.test import TestCase
from django.utils import translation

from campings.models import Camping
from core.i18n import translate_value
from panel.forms import ProfileForm

from .factories import make_camping


class TranslateValueTests(TestCase):
    def test_prefers_active_language_then_fallbacks(self):
        value = {"es": "Hola", "en": "Hello"}
        with translation.override("en"):
            self.assertEqual(translate_value(value), "Hello")
        with translation.override("de"):
            self.assertEqual(translate_value(value), "Hola")  # platform default (es)
        with translation.override("de"):
            self.assertEqual(translate_value({"fr": "Bonjour"}), "Bonjour")
        self.assertEqual(translate_value({}), "")
        self.assertEqual(translate_value("plain"), "plain")

    def test_camping_default_language_is_used_as_fallback(self):
        value = {"en": "Hello", "fr": "Bonjour"}
        with translation.override("de"):
            self.assertEqual(translate_value(value, fallback="fr"), "Bonjour")


class TranslatedFormFieldTests(TestCase):
    def setUp(self):
        self.camping = make_camping(languages=["es", "en"], default_language="es")

    def data(self, **overrides):
        data = {"name": "Camping Test", "tagline_es": "Lema", "tagline_en": "Tagline", "description_es": "Texto"}
        data.update(overrides)
        return data

    def test_fields_follow_camping_languages(self):
        form = ProfileForm(instance=self.camping, camping=self.camping)
        html = str(form["tagline"])
        self.assertIn('name="tagline_es"', html)
        self.assertIn('name="tagline_en"', html)
        self.assertNotIn('name="tagline_fr"', html)

    def test_saves_one_value_per_language_and_drops_empty_ones(self):
        form = ProfileForm(self.data(tagline_en="  "), instance=self.camping, camping=self.camping)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.camping.refresh_from_db()
        self.assertEqual(self.camping.tagline, {"es": "Lema"})
        self.assertEqual(self.camping.description, {"es": "Texto"})

    def test_hidden_languages_are_preserved(self):
        self.camping.tagline = {"es": "Lema", "fr": "Devise"}
        self.camping.save()
        form = ProfileForm(self.data(), instance=self.camping, camping=self.camping)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.camping.refresh_from_db()
        self.assertEqual(self.camping.tagline, {"es": "Lema", "en": "Tagline", "fr": "Devise"})


class CampingLanguagesTests(TestCase):
    def test_default_language_is_always_first_and_invalid_codes_are_dropped(self):
        camping = Camping.objects.create(name="X", default_language="fr", languages=["en", "xx", "fr", "en"])
        self.assertEqual(camping.languages, ["fr", "en"])
        self.assertEqual(camping.content_languages, ["fr", "en"])

    def test_slug_is_generated_and_unique(self):
        first = Camping.objects.create(name="Camping El Pinar")
        second = Camping.objects.create(name="Camping El Pinar")
        self.assertEqual(first.slug, "camping-el-pinar")
        self.assertEqual(second.slug, "camping-el-pinar-2")

    def test_reserved_slug_is_avoided(self):
        self.assertEqual(Camping.objects.create(name="Panel").slug, "panel-camping")
