"""Canonical identity and substitute families. Fixture aliases are verified, not fuzzy merges."""

import re

# name, price, landed cost, category/family, baseline propensity, trajectory
SPECS = {
    "hypermarket": [
        ("Rice 5 kg", 520, 430, "essentials", 0.16, "steady"),
        ("Sunflower oil 1 L", 150, 132, "essentials", 0.2, "steady"),
        ("Milk 1 L", 64, 55, "chilled", 0.3, "steady"),
        ("Potato chips 50 g", 20, 14, "snacks", 0.25, "steady"),
        ("Instant noodles 280 g", 72, 54, "pantry", 0.21, "steady"),
        ("Chocolate 100 g", 90, 55, "snacks", 0.12, "steady"),
        ("Oats 1 kg", 180, 120, "breakfast", 0.1, "rising"),
        ("Fruit juice 1 L", 110, 76, "drinks", 0.14, "falling"),
        ("Digestive biscuits 200 g", 80, 55, "snacks", 0.07, "dead"),
        ("Breakfast cereal 300 g", 170, 126, "breakfast", 0.12, "steady"),
        ("Millet cookies 150 g", 110, 68, "snacks", 0.19, "candidate"),
        ("Roasted makhana 80 g", 130, 83, "snacks", 0.15, "candidate"),
    ],
    "restaurant": [
        ("Veg thali", 220, 95, "mains", 0.25, "steady"),
        ("Masala dosa", 140, 55, "mains", 0.18, "rising"),
        ("Dal rice", 160, 60, "mains", 0.2, "steady"),
        ("Veg burger", 120, 55, "mains", 0.14, "falling"),
        ("French fries", 90, 35, "sides", 0.21, "steady"),
        ("Lime soda", 60, 15, "drinks", 0.3, "steady"),
        ("Gulab jamun", 70, 22, "desserts", 0.16, "steady"),
        ("Filter coffee", 80, 24, "drinks", 0.25, "steady"),
        ("Cream pasta", 240, 110, "mains", 0.08, "dead"),
        ("Idli plate", 100, 35, "mains", 0.18, "steady"),
        ("Paneer grain bowl", 260, 110, "mains", 0.2, "candidate"),
        ("Veg rice bowl", 210, 84, "mains", 0.23, "candidate"),
    ],
    "apparel": [
        ("Cotton tee M", 399, 190, "casual", 0.28, "steady"),
        ("Denim jeans 32", 1299, 650, "bottoms", 0.18, "steady"),
        ("Linen shirt M", 899, 420, "casual", 0.17, "rising"),
        ("Printed tee M", 499, 230, "casual", 0.17, "falling"),
        ("Chinos 32", 1099, 540, "bottoms", 0.14, "steady"),
        ("Kurta M", 999, 460, "ethnic", 0.2, "steady"),
        ("Leggings M", 349, 150, "bottoms", 0.22, "steady"),
        ("Scarf", 299, 100, "accessories", 0.16, "steady"),
        ("Neon slogan tee M", 599, 290, "casual", 0.06, "dead"),
        ("Socks pair", 149, 55, "accessories", 0.3, "steady"),
        ("Oversized tee M", 699, 310, "casual", 0.23, "candidate"),
        ("Polo tee M", 799, 340, "casual", 0.19, "candidate"),
    ],
    "kirana": [
        ("Rice 1 kg", 65, 52, "staples", 0.3, "steady"),
        ("Atta 5 kg", 240, 195, "staples", 0.21, "steady"),
        ("Toor dal 1 kg", 150, 123, "staples", 0.22, "rising"),
        ("Salt 1 kg", 25, 18, "staples", 0.18, "steady"),
        ("Tea 250 g", 130, 100, "pantry", 0.2, "steady"),
        ("Biscuits 100 g", 20, 14, "snacks", 0.25, "steady"),
        ("Old candy pack", 40, 25, "snacks", 0.03, "dead"),
        ("Ragi cookies 150 g", 85, 52, "snacks", 0.15, "candidate"),
        ("Peanuts 100 g", 35, 22, "snacks", 0.2, "candidate"),
    ],
    "pharmacy": [
        ("Paracetamol strip", 30, 20, "otc", 0.25, "steady"),
        ("ORS sachet", 22, 14, "otc", 0.22, "steady"),
        ("Bandage pack", 65, 37, "first-aid", 0.14, "steady"),
        ("Hand sanitiser 100 ml", 60, 32, "hygiene", 0.1, "falling"),
        ("Sunscreen 50 g", 349, 220, "care", 0.12, "rising"),
        ("Soap bar", 45, 29, "hygiene", 0.3, "steady"),
        ("Legacy vitamin pack", 180, 110, "care", 0.05, "dead"),
        ("Moisturiser 100 ml", 220, 130, "care", 0.15, "candidate"),
        ("Lip balm 10 g", 99, 48, "care", 0.18, "candidate"),
    ],
    "bakery": [
        ("Sourdough loaf", 160, 65, "bread", 0.24, "rising"),
        ("Milk bread loaf", 55, 25, "bread", 0.3, "steady"),
        ("Croissant", 95, 35, "pastry", 0.24, "steady"),
        ("Chocolate muffin", 75, 27, "pastry", 0.2, "steady"),
        ("Veg puff", 35, 13, "savoury", 0.3, "steady"),
        ("Tea cake", 140, 55, "cake", 0.14, "falling"),
        ("Fruit muffin", 85, 32, "pastry", 0.06, "dead"),
        ("Banana muffin", 80, 29, "pastry", 0.2, "candidate"),
        ("Cinnamon roll", 110, 40, "pastry", 0.19, "candidate"),
    ],
    "electronics": [
        ("USB C cable 1 m", 299, 130, "accessories", 0.3, "steady"),
        ("Charger 20 W", 799, 390, "accessories", 0.2, "steady"),
        ("Wireless earbuds", 1499, 820, "audio", 0.19, "rising"),
        ("Wired earphones", 299, 130, "audio", 0.17, "falling"),
        ("Power bank 10k", 1299, 700, "accessories", 0.18, "steady"),
        ("Phone stand", 199, 65, "accessories", 0.25, "steady"),
        ("Micro USB cable 1 m", 249, 100, "accessories", 0.05, "dead"),
        ("USB C cable 2 m", 449, 190, "accessories", 0.25, "candidate"),
        ("Fast charger 30 W", 999, 480, "accessories", 0.16, "candidate"),
    ],
}
NAMES = {
    "hypermarket": "Asha Hypermarket",
    "restaurant": "Annapurna Kitchen",
    "apparel": "Thread & Co.",
    "kirana": "Patel Kirana",
    "pharmacy": "Carewell Pharmacy",
    "bakery": "Rise Bakery",
    "electronics": "Circuit Corner",
}
RECIPES = {
    "Veg thali": {"rice": 0.15, "lentils": 0.08, "vegetables": 0.18},
    "Masala dosa": {"batter": 0.2, "vegetables": 0.1},
    "Dal rice": {"rice": 0.18, "lentils": 0.1},
    "Veg burger": {"bread": 0.1, "vegetables": 0.15},
    "French fries": {"potatoes": 0.18},
    "Lime soda": {"lime": 0.05},
    "Gulab jamun": {"dessert_mix": 0.07},
    "Filter coffee": {"coffee": 0.015, "milk": 0.12},
    "Cream pasta": {"pasta": 0.12, "cream": 0.08},
    "Idli plate": {"batter": 0.18},
    "Paneer grain bowl": {"rice": 0.12, "paneer": 0.1, "vegetables": 0.18},
    "Veg rice bowl": {"rice": 0.16, "vegetables": 0.2},
}
INGREDIENTS = {
    "rice": 25.0,
    "lentils": 12.0,
    "vegetables": 20.0,
    "batter": 22.0,
    "bread": 8.0,
    "potatoes": 14.0,
    "lime": 5.0,
    "dessert_mix": 6.0,
    "coffee": 2.0,
    "milk": 12.0,
    "pasta": 8.0,
    "cream": 5.0,
    "paneer": 8.0,
}


def catalogue(kind):
    return [
        dict(
            id=f"{kind}-{i + 1:02}",
            name=s[0],
            price=s[1],
            cost=s[2],
            family=s[3],
            propensity=s[4],
            trend=s[5],
            candidate=s[5] == "candidate",
            unit="portion" if kind == "restaurant" else "pack",
            aliases=[s[0], s[0].lower().replace(" ", "-"), f"{kind.upper()}-{i + 1:02}"],
            mapping_confidence=1.0,
            mapping_source="curated synthetic catalogue",
            recipe=RECIPES.get(s[0], {}),
        )
        for i, s in enumerate(SPECS[kind])
    ]


def normalise(text):
    return re.sub(r"[^a-z0-9]", "", text.lower())


def resolve(text, kind):
    """Only exact catalogue ID/alias matches. Different packs and variants never collapse."""
    matches = [
        p
        for p in catalogue(kind)
        if normalise(text) in {normalise(p["id"]), *(normalise(a) for a in p["aliases"])}
    ]
    return matches[0] if len(matches) == 1 else None
