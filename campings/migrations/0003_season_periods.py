import re

import django.db.models.deletion
from django.db import migrations, models

KIND_PATTERNS = [
    ("special", r"semana santa|pascua|easter|p[âa]ques|ostern|pasen|pasqua|puente|navidad|christmas|no[eë]l|fiesta|festival"),
    ("low", r"baja|low|basse|nieder|neben|laag|bassa"),
    ("high", r"alta|high|haute|hoch|haupt|hoog"),
    ("mid", r"media|medio|mid|moyenne|mittel|zwischen|midden"),
]


def infer_kind(names):
    text = " ".join(str(value) for value in (names or {}).values()).lower()
    for kind, pattern in KIND_PATTERNS:
        if re.search(pattern, text):
            return kind
    return "mid"


def dates_to_periods(apps, schema_editor):
    Season = apps.get_model("campings", "Season")
    SeasonPeriod = apps.get_model("campings", "SeasonPeriod")
    for season in Season.objects.all():
        SeasonPeriod.objects.create(season=season, start_date=season.start_date, end_date=season.end_date)
        season.kind = infer_kind(season.name)
        season.save(update_fields=["kind"])


def periods_to_dates(apps, schema_editor):
    Season = apps.get_model("campings", "Season")
    for season in Season.objects.all():
        periods = list(season.periods.order_by("start_date"))
        if periods:
            season.start_date = periods[0].start_date
            season.end_date = periods[-1].end_date
            season.save(update_fields=["start_date", "end_date"])


class Migration(migrations.Migration):
    dependencies = [
        ("campings", "0002_own_website"),
    ]

    operations = [
        migrations.CreateModel(
            name="SeasonPeriod",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("start_date", models.DateField(verbose_name="from")),
                ("end_date", models.DateField(verbose_name="to (inclusive)")),
                (
                    "season",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="periods",
                        to="campings.season",
                        verbose_name="season",
                    ),
                ),
            ],
            options={
                "verbose_name": "period",
                "verbose_name_plural": "periods",
                "ordering": ["start_date"],
            },
        ),
        migrations.AddField(
            model_name="season",
            name="kind",
            field=models.CharField(
                choices=[
                    ("low", "Low season"),
                    ("mid", "Mid season"),
                    ("high", "High season"),
                    ("special", "Special period"),
                ],
                default="mid",
                max_length=10,
                verbose_name="type",
            ),
        ),
        migrations.AlterField(
            model_name="season",
            name="start_date",
            field=models.DateField(null=True, verbose_name="from"),
        ),
        migrations.AlterField(
            model_name="season",
            name="end_date",
            field=models.DateField(null=True, verbose_name="to (inclusive)"),
        ),
        migrations.RunPython(dates_to_periods, periods_to_dates),
        migrations.RemoveField(model_name="season", name="start_date"),
        migrations.RemoveField(model_name="season", name="end_date"),
        migrations.AlterModelOptions(
            name="season",
            options={
                "ordering": [
                    models.Case(
                        models.When(kind="low", then=models.Value(0)),
                        models.When(kind="mid", then=models.Value(1)),
                        models.When(kind="high", then=models.Value(2)),
                        default=models.Value(3),
                    ),
                    "id",
                ],
                "verbose_name": "season",
                "verbose_name_plural": "seasons",
            },
        ),
    ]
