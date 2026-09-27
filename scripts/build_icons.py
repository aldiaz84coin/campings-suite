"""Build ``static/icons/sprite.svg`` from Lucide (ISC) and Simple Icons (CC0).

Usage (from the project root)::

    npm pack lucide-static simple-icons
    mkdir -p /tmp/icons && tar xzf lucide-static-*.tgz -C /tmp/icons \
        && mkdir -p /tmp/icons/si && tar xzf simple-icons-*.tgz -C /tmp/icons/si
    python scripts/build_icons.py /tmp/icons/package/icons /tmp/icons/si/package/icons

Add names to ``LUCIDE`` / ``BRANDS`` to make more icons available to the
``{% icon "name" %}`` template tag.
"""

import re
import sys
from pathlib import Path

LUCIDE = sorted(
    {
        # Facilities & amenities (campings/catalog.py)
        "accessibility",
        "baby",
        "banknote",
        "bath",
        "bed",
        "bed-double",
        "beer",
        "bike",
        "building",
        "building-2",
        "bus",
        "cable",
        "car",
        "caravan",
        "clock",
        "coffee",
        "cooking-pot",
        "croissant",
        "dog",
        "droplet",
        "droplets",
        "dumbbell",
        "ferris-wheel",
        "fish",
        "flame",
        "footprints",
        "gamepad-2",
        "goal",
        "heart",
        "heart-pulse",
        "heater",
        "house",
        "kayak",
        "lock",
        "map",
        "motorbike",
        "mountain",
        "music",
        "party-popper",
        "paw-print",
        "pizza",
        "plug-zap",
        "puzzle",
        "receipt",
        "recycle",
        "refrigerator",
        "shirt",
        "shopping-cart",
        "shower-head",
        "snowflake",
        "sparkles",
        "spray-can",
        "square-parking",
        "store",
        "sun",
        "tag",
        "tent",
        "tent-tree",
        "thermometer-sun",
        "ticket",
        "toilet",
        "tree-palm",
        "tree-pine",
        "trees",
        "tv",
        "user",
        "users",
        "utensils",
        "van",
        "volleyball",
        "washing-machine",
        "waves",
        "waves-ladder",
        "wifi",
        "wine",
        # Interface
        "arrow-down",
        "arrow-left",
        "arrow-right",
        "arrow-up",
        "ban",
        "calendar",
        "calendar-check",
        "calendar-days",
        "calendar-range",
        "check",
        "chevron-down",
        "chevron-left",
        "chevron-right",
        "chevron-up",
        "circle-alert",
        "circle-check",
        "circle-help",
        "circle-x",
        "copy",
        "credit-card",
        "euro",
        "external-link",
        "eye",
        "eye-off",
        "file-text",
        "globe",
        "grip-vertical",
        "hourglass",
        "image",
        "images",
        "inbox",
        "info",
        "key-round",
        "languages",
        "layout-dashboard",
        "link",
        "list-checks",
        "log-in",
        "log-out",
        "mail",
        "map-pin",
        "maximize",
        "menu",
        "message-circle",
        "moon",
        "palette",
        "pencil",
        "phone",
        "plus",
        "ruler",
        "scroll-text",
        "search",
        "send",
        "settings",
        "shield-check",
        "sliders-horizontal",
        "star",
        "trash-2",
        "upload",
        "user-plus",
        "wallet",
        "x",
    }
)
BRANDS = {"instagram": "instagram", "facebook": "facebook", "whatsapp": "whatsapp"}

STROKE_ATTRS = 'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"'


def inner_svg(markup):
    markup = re.sub(r"<!--.*?-->", "", markup, flags=re.S)
    markup = re.sub(r"<title>.*?</title>", "", markup, flags=re.S)
    body = re.search(r"<svg[^>]*>(.*)</svg>", markup, flags=re.S).group(1)
    return re.sub(r"\s+", " ", body).strip()


def main(lucide_dir, brands_dir):
    lucide_dir, brands_dir = Path(lucide_dir), Path(brands_dir)
    symbols = []
    for name in LUCIDE:
        body = inner_svg((lucide_dir / f"{name}.svg").read_text())
        symbols.append(f'<symbol id="{name}" viewBox="0 0 24 24" {STROKE_ATTRS}>{body}</symbol>')
    for name, source in sorted(BRANDS.items()):
        body = inner_svg((brands_dir / f"{source}.svg").read_text())
        symbols.append(f'<symbol id="{name}" viewBox="0 0 24 24" fill="currentColor" stroke="none">{body}</symbol>')
    sprite = (
        '<svg xmlns="http://www.w3.org/2000/svg">\n'
        "<!-- Icons: Lucide (ISC License, https://lucide.dev) and Simple Icons (CC0, https://simpleicons.org) -->\n"
        + "\n".join(symbols)
        + "\n</svg>\n"
    )
    target = Path(__file__).resolve().parent.parent / "static" / "icons" / "sprite.svg"
    target.write_text(sprite)
    print(f"Wrote {len(symbols)} icons to {target}")


if __name__ == "__main__":
    main(*sys.argv[1:3])
