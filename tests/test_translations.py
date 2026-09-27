import gettext
from pathlib import Path

import polib
from django.conf import settings
from django.test import SimpleTestCase, TestCase
from django.utils import translation

from .factories import make_camping


class CatalogueTests(SimpleTestCase):
    def test_compiled_catalogues_match_the_po_files(self):
        """Fails if someone edits a .po file and forgets to compile it."""
        for po_path in Path(settings.LOCALE_PATHS[0]).glob("*/LC_MESSAGES/django.po"):
            mo_path = po_path.with_suffix(".mo")
            self.assertTrue(mo_path.exists(), mo_path)
            with open(mo_path, "rb") as handle:
                compiled = gettext.GNUTranslations(handle)
            for entry in polib.pofile(str(po_path)).translated_entries():
                if entry.msgid_plural:
                    self.assertEqual(compiled.ngettext(entry.msgid, entry.msgid_plural, 1), entry.msgstr_plural[0])
                else:
                    self.assertEqual(compiled.gettext(entry.msgid), entry.msgstr, f"{po_path}: {entry.msgid}")

    def test_every_platform_language_has_a_catalogue(self):
        for code, _name in settings.LANGUAGES:
            if code != "en":
                self.assertTrue((Path(settings.LOCALE_PATHS[0]) / code / "LC_MESSAGES" / "django.mo").exists(), code)


class TranslatedPagesTests(TestCase):
    def test_public_pages_are_translated(self):
        camping = make_camping("Camping Idiomas")
        expectations = {
            "es": "Encuentra tu sitio bajo las estrellas",
            "fr": "Trouvez votre place sous les étoiles",
            "de": "Finden Sie Ihren Platz unter den Sternen",
            "nl": "Vind jouw plek onder de sterren",
            "it": "Trova il tuo posto sotto le stelle",
            "en": "Find your place under the stars",
        }
        for code, text in expectations.items():
            self.assertContains(self.client.get(f"/{code}/"), text)
        self.assertContains(self.client.get(f"/de/camping/{camping.slug}/"), "Buchung anfragen")

    def test_quote_labels_follow_the_language(self):
        from campings.pricing import nights_label

        with translation.override("es"):
            self.assertEqual(nights_label(3), "3 noches")
        with translation.override("fr"):
            self.assertEqual(nights_label(1), "1 nuit")
