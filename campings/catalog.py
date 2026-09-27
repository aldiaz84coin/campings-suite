"""Predefined, translatable catalogues used by campings.

Each entry has a stable key (stored in the database), a label translated
with gettext and an icon from ``static/icons/sprite.svg``.
"""

from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy

# --- Facilities (instalaciones) -----------------------------------------------

FACILITY_GROUPS = [
    ("services", _("Services")),
    ("leisure", _("Leisure & sports")),
    ("sanitary", _("Sanitary facilities")),
    ("pitches", _("Pitches & vehicles")),
    ("surroundings", _("Surroundings")),
]

# key, label, icon, group
FACILITIES = [
    ("reception_24h", _("24-hour reception"), "clock", "services"),
    ("wifi", _("Wi-Fi"), "wifi", "services"),
    ("restaurant", _("Restaurant"), "utensils", "services"),
    ("bar", _("Bar"), "beer", "services"),
    ("supermarket", _("Supermarket"), "shopping-cart", "services"),
    ("bakery", _("Fresh bread"), "croissant", "services"),
    ("takeaway", _("Takeaway food"), "pizza", "services"),
    ("laundry", _("Laundry"), "washing-machine", "services"),
    ("fridge_rental", _("Fridge rental"), "refrigerator", "services"),
    ("safe", _("Safe deposit boxes"), "lock", "services"),
    ("atm", _("Cash machine"), "banknote", "services"),
    ("first_aid", _("First aid"), "heart-pulse", "services"),
    ("pool", _("Swimming pool"), "waves-ladder", "leisure"),
    ("kids_pool", _("Children's pool"), "waves", "leisure"),
    ("heated_pool", _("Heated indoor pool"), "thermometer-sun", "leisure"),
    ("playground", _("Playground"), "ferris-wheel", "leisure"),
    ("kids_club", _("Kids club"), "puzzle", "leisure"),
    ("entertainment", _("Entertainment programme"), "party-popper", "leisure"),
    ("sports_ground", _("Sports ground"), "volleyball", "leisure"),
    ("tennis", _("Tennis / padel"), "goal", "leisure"),
    ("gym", _("Gym"), "dumbbell", "leisure"),
    ("spa", _("Spa & wellness"), "sparkles", "leisure"),
    ("games_room", _("Games room"), "gamepad-2", "leisure"),
    ("bike_rental", _("Bike rental"), "bike", "leisure"),
    ("water_sports", _("Water sports"), "kayak", "leisure"),
    ("bbq", _("Barbecue area"), "flame", "leisure"),
    ("hot_showers", _("Hot showers"), "shower-head", "sanitary"),
    ("toilets", _("Toilet blocks"), "toilet", "sanitary"),
    ("accessible", _("Accessible facilities"), "accessibility", "sanitary"),
    ("baby_room", _("Baby changing room"), "baby", "sanitary"),
    ("dishwashing", _("Dishwashing area"), "droplets", "sanitary"),
    ("electricity", _("Electrical hook-up"), "plug-zap", "pitches"),
    ("water_points", _("Drinking water points"), "droplet", "pitches"),
    ("motorhome_service", _("Motorhome service area"), "caravan", "pitches"),
    ("chemical_disposal", _("Chemical toilet disposal"), "recycle", "pitches"),
    ("shade", _("Shaded pitches"), "tree-pine", "pitches"),
    ("parking", _("Parking"), "square-parking", "pitches"),
    ("ev_charging", _("EV charging point"), "cable", "pitches"),
    ("pets", _("Pets welcome"), "dog", "pitches"),
    ("dog_area", _("Dog park / dog shower"), "paw-print", "pitches"),
    ("beach", _("Beach nearby"), "tree-palm", "surroundings"),
    ("river", _("River or lake"), "fish", "surroundings"),
    ("mountain", _("Mountain setting"), "mountain", "surroundings"),
    ("hiking", _("Hiking trails"), "footprints", "surroundings"),
    ("town", _("Town nearby"), "building-2", "surroundings"),
    ("public_transport", _("Public transport"), "bus", "surroundings"),
]

FACILITY_MAP = {key: {"label": label, "icon": icon, "group": group} for key, label, icon, group in FACILITIES}
CUSTOM_FACILITY_ICONS = [
    ("sparkles", _("Generic")),
    ("tent", _("Tent")),
    ("trees", _("Nature")),
    ("sun", pgettext_lazy("icon", "Sun")),
    ("utensils", _("Food")),
    ("music", _("Music")),
    ("ticket", _("Activities")),
    ("heart", _("Wellness")),
    ("map", _("Excursions")),
    ("store", _("Shop")),
    ("wine", _("Wine & drinks")),
    ("footprints", _("Walks")),
]

# --- Accommodation ---------------------------------------------------------

ACCOMMODATION_KINDS = [
    ("pitch", _("Pitch"), "tent"),
    ("bungalow", _("Bungalow"), "house"),
    ("mobile_home", _("Mobile home"), "caravan"),
    ("cabin", _("Wooden cabin"), "tent-tree"),
    ("glamping", _("Glamping tent"), "tent"),
    ("tent_rental", _("Rental tent"), "tent"),
    ("caravan_rental", _("Rental caravan"), "caravan"),
    ("apartment", _("Apartment"), "building"),
    ("room", _("Room"), "bed-double"),
    ("other", _("Other"), "house"),
]
ACCOMMODATION_KIND_CHOICES = [(key, label) for key, label, _icon in ACCOMMODATION_KINDS]
ACCOMMODATION_KIND_ICONS = {key: icon for key, _label, icon in ACCOMMODATION_KINDS}

AMENITIES = [
    ("electricity", _("Electricity"), "plug-zap"),
    ("water", _("Water connection"), "droplet"),
    ("drainage", _("Drainage"), "droplets"),
    ("shade", _("Shade"), "tree-pine"),
    ("private_bathroom", _("Private bathroom"), "bath"),
    ("kitchen", _("Kitchen"), "cooking-pot"),
    ("air_conditioning", _("Air conditioning"), "snowflake"),
    ("heating", _("Heating"), "heater"),
    ("terrace", _("Terrace"), "sun"),
    ("bbq", _("Barbecue"), "flame"),
    ("tv", _("TV"), "tv"),
    ("wifi", _("Wi-Fi"), "wifi"),
    ("bed_linen", _("Bed linen included"), "bed"),
    ("towels", _("Towels included"), "shirt"),
    ("pets", _("Pets allowed"), "dog"),
    ("sea_view", _("Sea view"), "waves"),
    ("car_space", _("Car space"), "car"),
    ("accessible", _("Accessible"), "accessibility"),
]
AMENITY_CHOICES = [(key, label) for key, label, _icon in AMENITIES]
AMENITY_MAP = {key: {"label": label, "icon": icon} for key, label, icon in AMENITIES}

# --- Prices ----------------------------------------------------------------

ACCOMMODATION_PRICE_UNITS = [
    ("night", _("per night")),
    ("person_night", _("per person / night")),
]

SERVICE_UNITS = [
    ("night", _("per night")),
    ("stay", _("per stay")),
    ("adult_night", _("per adult / night")),
    ("child_night", _("per child / night")),
    ("person_night", _("per person / night")),
    ("person_stay", _("per person / stay")),
    ("pet_night", _("per pet / night")),
]
PER_NIGHT_UNITS = {"night", "adult_night", "child_night", "person_night", "pet_night"}

SERVICE_MODES = [
    ("optional", _("Optional extra (the guest chooses it)")),
    ("mandatory", _("Always charged (e.g. people, tourist tax)")),
    ("included", _("Included / information only")),
]

SERVICE_ICONS = [
    ("tag", _("Generic")),
    ("user", _("Adult")),
    ("baby", _("Child")),
    ("dog", _("Pet")),
    ("car", _("Car")),
    ("motorbike", _("Motorbike")),
    ("tent", _("Tent")),
    ("caravan", _("Caravan")),
    ("van", _("Camper van / motorhome")),
    ("plug-zap", _("Electricity")),
    ("receipt", _("Tax")),
    ("bed", _("Bed linen")),
    ("shirt", _("Towels")),
    ("spray-can", _("Cleaning")),
    ("coffee", _("Breakfast")),
    ("clock", _("Late check-out")),
    ("bike", _("Bike")),
    ("users", _("Visitor")),
    ("refrigerator", _("Fridge")),
    ("flame", _("Barbecue")),
]

CURRENCIES = [("EUR", "EUR €"), ("GBP", "GBP £"), ("USD", "USD $"), ("CHF", "CHF")]

PAYMENT_METHODS = [
    ("cash", _("Cash")),
    ("card", _("Credit / debit card")),
    ("transfer", _("Bank transfer")),
    ("bizum", _("Bizum")),
    ("paypal", _("PayPal")),
]
PAYMENT_METHOD_MAP = dict(PAYMENT_METHODS)

FONT_STYLES = [
    ("modern", _("Modern (sans-serif)")),
    ("classic", _("Classic (serif)")),
    ("rounded", _("Friendly (rounded)")),
]
