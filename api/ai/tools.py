import re

PATTERNS = [
    ("loan", r"loan|credit|karz|कर्ज|उधार"),
    ("promo", r"discount|offer|promo|छूट|सवलत"),
    ("cash", r"cash|runway|paisa|paise|पैस|नकद|gap|रोकड"),
    ("peers", r"peer|lookalike|similar|दुकानें|इतर दुक"),
    ("overview", r"kaisa|overview|summary|sales|बिक्री|विक्री|आज|aaj"),
    ("allocate", r"restock|stock|budget|खरीद|माल|साठा|next|rupee|रुपय"),
]


def route(text):
    for tool, pattern in PATTERNS:
        if re.search(pattern, text.lower()):
            return tool
    return "out_of_scope"
