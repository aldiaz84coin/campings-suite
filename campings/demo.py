"""Demo content: a complete example camping with generated illustrations."""

import random
from datetime import date, time, timedelta
from decimal import Decimal
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image, ImageDraw, ImageFilter

from core.images import process_photo

from .models import (
    AccommodationRate,
    AccommodationType,
    BookingPolicy,
    Camping,
    Facility,
    Photo,
    Season,
    SeasonPeriod,
    Service,
    ServiceRate,
)
from .seasons import easter_sunday

PALETTES = {
    "day": {
        "sky": ((125, 190, 235), (228, 243, 250)),
        "far": (120, 160, 140),
        "near": (58, 110, 80),
        "sun": (255, 236, 170),
    },
    "sunset": {
        "sky": ((247, 145, 92), (252, 214, 150)),
        "far": (150, 104, 110),
        "near": (80, 62, 80),
        "sun": (255, 244, 200),
    },
    "dawn": {
        "sky": ((164, 186, 226), (250, 214, 196)),
        "far": (126, 142, 170),
        "near": (72, 96, 120),
        "sun": (255, 232, 205),
    },
    "sea": {
        "sky": ((96, 176, 230), (205, 236, 250)),
        "far": (46, 128, 170),
        "near": (230, 208, 160),
        "sun": (255, 250, 220),
    },
    "forest": {
        "sky": ((170, 210, 200), (236, 246, 230)),
        "far": (84, 140, 100),
        "near": (36, 86, 58),
        "sun": (250, 248, 220),
    },
    "night": {"sky": ((24, 34, 70), (70, 80, 130)), "far": (44, 52, 90), "near": (22, 28, 50), "sun": (250, 246, 220)},
}


def _vertical_gradient(size, top, bottom):
    width, height = size
    image = Image.new("RGB", size)
    draw = ImageDraw.Draw(image)
    for y in range(height):
        t = y / max(height - 1, 1)
        color = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        draw.line([(0, y), (width, y)], fill=color)
    return image


def _ridge(rng, width, base, amplitude, steps=9):
    points = [(0, base)]
    for i in range(1, steps):
        points.append((width * i / (steps - 1), base - rng.uniform(0.2, 1.0) * amplitude))
    return points


def generate_scene(kind="day", subject="tent", seed=1, size=(1600, 1066)):
    """A simple flat illustration (sky, hills, trees and a tent or cabin)."""
    rng = random.Random(seed)
    palette = PALETTES[kind]
    width, height = size
    image = _vertical_gradient(size, *palette["sky"])
    draw = ImageDraw.Draw(image)

    sun_x, sun_y, radius = rng.randint(width // 5, 4 * width // 5), rng.randint(height // 8, height // 3), height // 12
    if kind == "night":
        for _ in range(120):
            x, y = rng.randint(0, width), rng.randint(0, height // 2)
            draw.ellipse([x, y, x + 3, y + 3], fill=(240, 240, 255))
    image.paste(Image.new("RGB", size, palette["sun"]), mask=_circle_mask(size, sun_x, sun_y, radius))
    draw = ImageDraw.Draw(image)

    far = _ridge(rng, width, height * 0.62, height * 0.22)
    draw.polygon([*far, (width, height), (0, height)], fill=palette["far"])
    if kind == "sea":
        draw.rectangle([0, int(height * 0.6), width, height], fill=(52, 140, 190))
        for y in range(int(height * 0.62), height, 14):
            draw.line(
                [(rng.randint(0, width // 3), y), (rng.randint(width // 2, width), y)], fill=(120, 190, 225), width=2
            )
        draw.polygon([(0, height * 0.82), (width, height * 0.74), (width, height), (0, height)], fill=palette["near"])
    else:
        near = _ridge(rng, width, height * 0.8, height * 0.14)
        draw.polygon([*near, (width, height), (0, height)], fill=palette["near"])
        tree_color = tuple(max(c - 25, 0) for c in palette["near"])
        for _ in range(rng.randint(14, 24)):
            x = rng.randint(0, width)
            h = rng.randint(height // 9, height // 4)
            base_y = rng.randint(int(height * 0.72), int(height * 0.95))
            draw.polygon([(x, base_y - h), (x - h // 4, base_y), (x + h // 4, base_y)], fill=tree_color)

    ground_y = int(height * 0.9)
    cx = rng.randint(width // 3, 2 * width // 3)
    if subject == "tent":
        w, h = width // 5, height // 4
        draw.polygon([(cx, ground_y - h), (cx - w // 2, ground_y), (cx + w // 2, ground_y)], fill=(233, 162, 59))
        draw.polygon([(cx, ground_y - h), (cx - w // 8, ground_y), (cx + w // 8, ground_y)], fill=(120, 70, 30))
    elif subject == "cabin":
        w, h = width // 4, height // 5
        draw.rectangle([cx - w // 2, ground_y - h, cx + w // 2, ground_y], fill=(150, 98, 60))
        draw.polygon(
            [(cx - w // 2 - 20, ground_y - h), (cx, ground_y - h - h // 2), (cx + w // 2 + 20, ground_y - h)],
            fill=(90, 56, 40),
        )
        draw.rectangle([cx - w // 8, ground_y - h // 2, cx + w // 8, ground_y], fill=(70, 44, 30))
        draw.rectangle(
            [cx + w // 5, ground_y - h * 3 // 4, cx + w // 5 + w // 8, ground_y - h // 2], fill=(255, 220, 140)
        )
    elif subject == "caravan":
        w, h = width // 4, height // 7
        draw.rounded_rectangle(
            [cx - w // 2, ground_y - h - 20, cx + w // 2, ground_y - 20], radius=30, fill=(245, 245, 240)
        )
        draw.rectangle([cx - w // 3, ground_y - h, cx - w // 3 + w // 5, ground_y - h + h // 2], fill=(110, 170, 210))
        draw.ellipse([cx - 30, ground_y - 50, cx + 30, ground_y + 10], fill=(40, 40, 40))
    elif subject == "pool":
        draw.rounded_rectangle(
            [width // 6, int(height * 0.8), 5 * width // 6, height - 20], radius=40, fill=(90, 200, 230)
        )
        for y in range(int(height * 0.82), height - 30, 18):
            draw.line([(width // 5, y), (4 * width // 5, y)], fill=(170, 230, 245), width=3)
    return image.filter(ImageFilter.SMOOTH)


def _circle_mask(size, x, y, radius):
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).ellipse([x - radius, y - radius, x + radius, y + radius], fill=255)
    return mask


def scene_upload(name, **kwargs):
    buffer = BytesIO()
    generate_scene(**kwargs).save(buffer, "JPEG", quality=88)
    return SimpleUploadedFile(f"{name}.jpg", buffer.getvalue(), content_type="image/jpeg")


def add_photo(camping, name, position, caption, accommodation=None, **scene):
    large, thumb = process_photo(scene_upload(name, **scene))
    photo = Photo(camping=camping, position=position, width=large.width, height=large.height, caption=caption)
    photo.accommodation = accommodation
    photo.image.save(large.file.name, large.file, save=False)
    photo.thumbnail.save(thumb.file.name, thumb.file, save=False)
    photo.save()
    return photo


def T(es, en, fr=None, de=None, nl=None, it=None):
    values = {"es": es, "en": en, "fr": fr, "de": de, "nl": nl, "it": it}
    return {code: text for code, text in values.items() if text}


def create_demo_camping(slug="los-pinos-demo", year=None, with_photos=True):
    """Create (or recreate) a fully configured demo camping and return it."""
    year = year or date.today().year
    Camping.objects.filter(slug=slug).delete()
    camping = Camping.objects.create(
        name="Camping Los Pinos",
        slug=slug,
        tagline=T(
            "Pinos, mar y calas a 300 metros de la playa",
            "Pine trees, sea and coves 300 metres from the beach",
            "Pins, mer et criques à 300 mètres de la plage",
            "Pinien, Meer und Buchten 300 Meter vom Strand",
            "Pijnbomen, zee en baaien op 300 meter van het strand",
            "Pini, mare e calette a 300 metri dalla spiaggia",
        ),
        description=T(
            "Camping familiar en plena Costa Brava, rodeado de un pinar centenario que da sombra natural a todas las parcelas.\n\n"
            "Disponemos de piscina con zona infantil, restaurante con terraza, supermercado y un programa de animación en verano. "
            "La playa y el centro del pueblo están a un agradable paseo.",
            "Family campsite on the Costa Brava, surrounded by a century-old pine forest that gives natural shade to every pitch.\n\n"
            "We have a swimming pool with a children's area, a restaurant with terrace, a supermarket and an entertainment "
            "programme in summer. The beach and the village centre are a pleasant walk away.",
            "Camping familial sur la Costa Brava, entouré d'une pinède centenaire qui ombrage naturellement tous les emplacements.\n\n"
            "Piscine avec espace enfants, restaurant avec terrasse, supérette et animations en été. "
            "La plage et le centre du village sont à quelques minutes à pied.",
            "Familiencampingplatz an der Costa Brava, umgeben von einem jahrhundertealten Pinienwald, der allen Stellplätzen "
            "natürlichen Schatten spendet.\n\nSchwimmbad mit Kinderbereich, Restaurant mit Terrasse, Supermarkt und "
            "Animationsprogramm im Sommer. Strand und Ortszentrum sind bequem zu Fuß erreichbar.",
            "Familiecamping aan de Costa Brava, omringd door een eeuwenoud dennenbos dat alle plaatsen natuurlijke schaduw geeft.\n\n"
            "Zwembad met kinderbad, restaurant met terras, supermarkt en animatie in de zomer. "
            "Het strand en het dorpscentrum liggen op loopafstand.",
            "Campeggio per famiglie sulla Costa Brava, circondato da una pineta secolare che offre ombra naturale a tutte le piazzole.\n\n"
            "Piscina con area bambini, ristorante con terrazza, minimarket e animazione in estate. "
            "La spiaggia e il centro del paese si raggiungono con una piacevole passeggiata.",
        ),
        location_info=T(
            "A 300 m de la playa y a 10 minutos a pie del centro. Salida 9 de la AP-7, dirección Tossa de Mar.",
            "300 m from the beach and a 10-minute walk from the centre. Exit 9 of the AP-7 motorway, towards Tossa de Mar.",
            "À 300 m de la plage et à 10 minutes à pied du centre. Sortie 9 de l'AP-7, direction Tossa de Mar.",
            "300 m vom Strand und 10 Gehminuten vom Zentrum. Ausfahrt 9 der AP-7, Richtung Tossa de Mar.",
        ),
        stars=3,
        email="info@campinglospinos.example",
        phone="+34 972 000 000",
        whatsapp="+34 600 000 000",
        website="https://campinglospinos.example",
        address="Carretera de la Costa, km 3",
        postal_code="17320",
        city="Tossa de Mar",
        region="Girona",
        country="España",
        latitude=Decimal("41.720600"),
        longitude=Decimal("2.930300"),
        opening_date=date(year, 3, 15),
        closing_date=date(year, 10, 31),
        default_language="es",
        languages=["es", "en", "fr", "de", "nl", "it"],
        legal_name="Càmping Los Pinos Costa Brava, S.L. (demo)",
        tax_id="B00000000",
        registry_info="Registro Mercantil de Girona, tomo 0000, folio 0, hoja GI-00000",
        tourism_registration="KG-000000",
        is_published=True,
        is_approved=True,
    )

    BookingPolicy.objects.filter(camping=camping).update(
        check_in_from=time(14, 0),
        check_in_until=time(21, 0),
        check_out_until=time(12, 0),
        min_nights=2,
        deposit_percent=30,
        free_cancellation_days=14,
        cancellation_fee_percent=50,
        pets_allowed=True,
        payment_methods=["card", "cash", "transfer", "bizum"],
        pets_text=T(
            "Perros admitidos con correa y cartilla de vacunación. Máximo 2 por parcela.",
            "Dogs welcome on a lead and with their vaccination record. Maximum 2 per pitch.",
            "Chiens acceptés en laisse avec carnet de vaccination. 2 maximum par emplacement.",
            "Hunde an der Leine und mit Impfpass willkommen. Maximal 2 pro Stellplatz.",
        ),
        rules_text=T(
            "Silencio de 23:00 a 8:00. Velocidad máxima de 10 km/h dentro del camping. Prohibido hacer fuego fuera de las zonas de barbacoa.",
            "Silence from 23:00 to 08:00. Maximum speed 10 km/h inside the camping. No fires outside the barbecue areas.",
            "Silence de 23h à 8h. Vitesse limitée à 10 km/h. Feux interdits en dehors des espaces barbecue.",
            "Nachtruhe von 23:00 bis 8:00 Uhr. Höchstgeschwindigkeit 10 km/h. Feuer nur in den Grillbereichen.",
        ),
    )

    pitch = AccommodationType.objects.create(
        camping=camping,
        kind="pitch",
        position=0,
        max_guests=6,
        size_m2=90,
        units=40,
        base_price=Decimal("16"),
        name=T(
            "Parcela con electricidad",
            "Pitch with electricity",
            "Emplacement avec électricité",
            "Stellplatz mit Strom",
            "Plaats met stroom",
            "Piazzola con elettricità",
        ),
        description=T(
            "Parcela sombreada de 80-100 m² con toma eléctrica de 10 A. Incluye un vehículo y una tienda o caravana.",
            "Shaded 80-100 m² pitch with a 10 A electrical hook-up. Includes one vehicle and one tent or caravan.",
            "Emplacement ombragé de 80-100 m² avec électricité 10 A. Comprend un véhicule et une tente ou caravane.",
            "Schattiger Stellplatz (80-100 m²) mit 10 A Stromanschluss. Inklusive ein Fahrzeug und ein Zelt oder Wohnwagen.",
        ),
        amenities=["electricity", "shade", "water", "car_space", "pets"],
    )
    bungalow = AccommodationType.objects.create(
        camping=camping,
        kind="bungalow",
        position=1,
        max_guests=5,
        size_m2=32,
        bedrooms=2,
        units=12,
        base_price=Decimal("75"),
        name=T("Bungalow Pino", "Pine bungalow", "Bungalow Pin", "Bungalow Pinie", "Bungalow Den", "Bungalow Pino"),
        description=T(
            "Bungalow de madera con dos habitaciones, baño, cocina equipada, aire acondicionado y terraza cubierta.",
            "Wooden bungalow with two bedrooms, bathroom, equipped kitchen, air conditioning and covered terrace.",
            "Bungalow en bois avec deux chambres, salle de bain, cuisine équipée, climatisation et terrasse couverte.",
            "Holzbungalow mit zwei Schlafzimmern, Bad, ausgestatteter Küche, Klimaanlage und überdachter Terrasse.",
        ),
        amenities=["private_bathroom", "kitchen", "air_conditioning", "terrace", "tv", "wifi", "bed_linen"],
    )
    glamping = AccommodationType.objects.create(
        camping=camping,
        kind="glamping",
        position=2,
        max_guests=2,
        size_m2=24,
        bedrooms=1,
        units=4,
        base_price=Decimal("95"),
        name=T(
            "Tienda Glamping Luna",
            "Moon glamping tent",
            "Tente glamping Lune",
            "Glamping-Zelt Mond",
            "Glampingtent Maan",
            "Tenda glamping Luna",
        ),
        description=T(
            "Tienda safari con cama de matrimonio, baño privado y terraza con vistas al pinar.",
            "Safari tent with a double bed, private bathroom and a terrace overlooking the pine forest.",
            "Tente safari avec lit double, salle de bain privée et terrasse face à la pinède.",
            "Safarizelt mit Doppelbett, eigenem Bad und Terrasse mit Blick auf den Pinienwald.",
        ),
        amenities=["private_bathroom", "terrace", "bed_linen", "towels", "wifi"],
    )
    season_specs = [
        (
            "low",
            T("Temporada baja", "Low season", "Basse saison", "Nebensaison", "Laagseizoen", "Bassa stagione"),
            "#3f8f6b",
            None,
            [((3, 15), (6, 14)), ((10, 1), (10, 31))],
        ),
        (
            "mid",
            T("Temporada media", "Mid season", "Moyenne saison", "Zwischensaison", "Middenseizoen", "Media stagione"),
            "#d69a2d",
            3,
            [((6, 15), (7, 14)), ((9, 1), (9, 30))],
        ),
        (
            "high",
            T("Temporada alta", "High season", "Haute saison", "Hauptsaison", "Hoogseizoen", "Alta stagione"),
            "#d4553a",
            5,
            [((7, 15), (8, 31))],
        ),
    ]
    seasons = []
    for kind, name, color, min_nights, ranges in season_specs:
        season = Season.objects.create(camping=camping, kind=kind, name=name, color=color, min_nights=min_nights)
        for season_year in (year, year + 1):
            for (m1, d1), (m2, d2) in ranges:
                SeasonPeriod.objects.create(
                    season=season, start_date=date(season_year, m1, d1), end_date=date(season_year, m2, d2)
                )
        seasons.append(season)
    easter = Season.objects.create(
        camping=camping,
        kind=Season.Kind.SPECIAL,
        name=T("Semana Santa", "Easter", "Pâques", "Ostern", "Pasen", "Pasqua"),
        color=Season.KIND_COLORS["special"],
        min_nights=3,
    )
    for season_year in (year, year + 1):
        sunday = easter_sunday(season_year)
        SeasonPeriod.objects.create(season=easter, start_date=sunday - timedelta(days=3), end_date=sunday)
    seasons.append(easter)
    # Low, mid, high and Easter prices per night.
    prices = {pitch: (14, 20, 29, 22), bungalow: (65, 95, 140, 110), glamping: (85, 110, 150, 125)}
    for accommodation, values in prices.items():
        for season, price in zip(seasons, values, strict=True):
            AccommodationRate.objects.create(accommodation=accommodation, season=season, price=Decimal(price))
    adult = Service.objects.create(
        camping=camping,
        position=0,
        icon="user",
        unit="adult_night",
        mode="mandatory",
        price=Decimal("6.5"),
        name=T("Adulto", "Adult", "Adulte", "Erwachsener", "Volwassene", "Adulto"),
    )
    child = Service.objects.create(
        camping=camping,
        position=1,
        icon="baby",
        unit="child_night",
        mode="mandatory",
        price=Decimal("4.5"),
        name=T(
            "Niño (3-10 años)",
            "Child (3-10 years)",
            "Enfant (3-10 ans)",
            "Kind (3-10 Jahre)",
            "Kind (3-10 jaar)",
            "Bambino (3-10 anni)",
        ),
    )
    for service in (adult, child):
        service.accommodations.add(pitch)
    Service.objects.create(
        camping=camping,
        position=2,
        icon="receipt",
        unit="adult_night",
        mode="mandatory",
        price=Decimal("1"),
        name=T(
            "Tasa turística", "Tourist tax", "Taxe de séjour", "Kurtaxe", "Toeristenbelasting", "Tassa di soggiorno"
        ),
    )
    dog = Service.objects.create(
        camping=camping,
        position=3,
        icon="dog",
        unit="pet_night",
        mode="mandatory",
        price=Decimal("3"),
        name=T("Perro", "Dog", "Chien", "Hund", "Hond", "Cane"),
    )
    Service.objects.create(
        camping=camping,
        position=4,
        icon="bed",
        unit="stay",
        mode="optional",
        price=Decimal("12"),
        name=T("Ropa de cama", "Bed linen", "Linge de lit", "Bettwäsche", "Beddengoed", "Biancheria da letto"),
    )
    Service.objects.create(
        camping=camping,
        position=5,
        icon="spray-can",
        unit="stay",
        mode="optional",
        price=Decimal("40"),
        name=T(
            "Limpieza final",
            "Final cleaning",
            "Ménage de fin de séjour",
            "Endreinigung",
            "Eindschoonmaak",
            "Pulizia finale",
        ),
    ).accommodations.add(bungalow)
    Service.objects.create(
        camping=camping,
        position=6,
        icon="wifi",
        unit="stay",
        mode="included",
        price=Decimal("0"),
        name=T("Wi-Fi", "Wi-Fi", "Wi-Fi", "WLAN", "Wifi", "Wi-Fi"),
    )
    high = seasons[2]
    ServiceRate.objects.create(service=adult, season=high, price=Decimal("8.5"))
    ServiceRate.objects.create(service=dog, season=high, price=Decimal("4"))

    for position, kind in enumerate(
        [
            "reception_24h",
            "wifi",
            "restaurant",
            "bar",
            "supermarket",
            "bakery",
            "laundry",
            "pool",
            "kids_pool",
            "playground",
            "entertainment",
            "sports_ground",
            "bbq",
            "hot_showers",
            "toilets",
            "accessible",
            "baby_room",
            "electricity",
            "motorhome_service",
            "shade",
            "pets",
            "beach",
            "hiking",
            "town",
        ]
    ):
        Facility.objects.create(camping=camping, kind=kind, position=position, is_paid=kind in {"laundry"})
    Facility.objects.create(
        camping=camping,
        kind="custom",
        icon="ticket",
        position=50,
        name=T(
            "Excursiones en kayak",
            "Kayak excursions",
            "Excursions en kayak",
            "Kajak-Ausflüge",
            "Kajaktochten",
            "Escursioni in kayak",
        ),
        description=T(
            "Salidas guiadas a las calas cada mañana en verano.", "Guided trips to the coves every morning in summer."
        ),
        is_paid=True,
    )

    if with_photos:
        shots = [
            (
                "pinos",
                T(
                    "El pinar al atardecer",
                    "The pine forest at sunset",
                    "La pinède au coucher du soleil",
                    "Der Pinienwald bei Sonnenuntergang",
                ),
                None,
                {"kind": "sunset", "subject": "tent"},
            ),
            (
                "playa",
                T(
                    "La cala a 300 metros",
                    "The cove 300 metres away",
                    "La crique à 300 mètres",
                    "Die Bucht in 300 Metern",
                ),
                None,
                {"kind": "sea", "subject": "none"},
            ),
            (
                "piscina",
                T(
                    "Piscina con zona infantil",
                    "Pool with children's area",
                    "Piscine avec espace enfants",
                    "Pool mit Kinderbereich",
                ),
                None,
                {"kind": "day", "subject": "pool"},
            ),
            (
                "parcela",
                T("Parcelas con sombra", "Shaded pitches", "Emplacements ombragés", "Schattige Stellplätze"),
                pitch,
                {"kind": "forest", "subject": "tent"},
            ),
            ("bungalow", T("Bungalow Pino", "Pine bungalow"), bungalow, {"kind": "dawn", "subject": "cabin"}),
            (
                "glamping",
                T("Tienda Glamping Luna", "Moon glamping tent"),
                glamping,
                {"kind": "night", "subject": "tent"},
            ),
            (
                "caravana",
                T("Zona de autocaravanas", "Motorhome area", "Aire de camping-cars", "Wohnmobilbereich"),
                pitch,
                {"kind": "day", "subject": "caravan"},
            ),
            (
                "bungalow-2",
                T("Terraza del bungalow", "Bungalow terrace"),
                bungalow,
                {"kind": "sunset", "subject": "cabin"},
            ),
        ]
        for position, (name, caption, accommodation, scene) in enumerate(shots):
            add_photo(camping, name, position, caption, accommodation, seed=position + 7, **scene)
    return camping
