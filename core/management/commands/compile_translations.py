from pathlib import Path

import polib
from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Compiles the project's .po catalogues into .mo files in pure Python "
        "(same result as compilemessages, without needing GNU gettext)."
    )

    def handle(self, *args, **options):
        count = 0
        for base in settings.LOCALE_PATHS:
            for po_path in sorted(Path(base).glob("*/LC_MESSAGES/*.po")):
                polib.pofile(str(po_path)).save_as_mofile(str(po_path.with_suffix(".mo")))
                count += 1
                self.stdout.write(f"Compiled {po_path.relative_to(settings.BASE_DIR)}")
        self.stdout.write(self.style.SUCCESS(f"{count} catalogue(s) compiled."))
