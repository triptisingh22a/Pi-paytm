"""Numeric authorization gate; no provider prompt can bypass it."""

import re
import unicodedata
from math import isclose

NUMBER = re.compile(r"(?<!\w)[−-]?\d+(?:[,.]\d+)*(?:[eE][+-]?\d+)?(?:\s*(?:[kK]|lakh|लाख|हजार))?(?:\s*%)?")
DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")


def normalize(text):
    return "".join(str(unicodedata.digit(c)) if c.isdigit() else c for c in text).replace("−", "-")


def tokens(text):
    text = normalize(str(text))
    dates = DATE.findall(text)
    text = DATE.sub("", text)
    result = []
    for item in NUMBER.findall(text):
        s = item.replace(",", "").replace(" ", "")
        multiplier = 1
        if s.endswith("%"):
            multiplier = 0.01
            s = s[:-1]
        for suffix, mult in [("lakh", 100000), ("लाख", 100000), ("हजार", 1000), ("K", 1000), ("k", 1000)]:
            if s.endswith(suffix):
                multiplier *= mult
                s = s[: -len(suffix)]
                break
        result.append(float(s) * multiplier)
    return result, dates


def authorized_values(data):
    values, dates = [], []
    if isinstance(data, dict):
        for val in data.values():
            v, d = authorized_values(val)
            values.extend(v)
            dates.extend(d)
    elif isinstance(data, (list, tuple)):
        for val in data:
            v, d = authorized_values(val)
            values.extend(v)
            dates.extend(d)
    elif isinstance(data, (int, float)) and not isinstance(data, bool):
        values.append(float(data))
    elif isinstance(data, str):
        v, d = tokens(data)
        values.extend(v)
        dates.extend(d)
    return values, dates


def check(reply, outputs):
    # Reject spelled-out numeric claims conservatively; templates use digits.
    if re.search(
        r"\b(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|twenty|thirty|forty|fifty|hundred|thousand|million)\b",
        reply.lower(),
    ):
        return False
    numbers, dates = tokens(reply)
    valid, allowed_dates = authorized_values(outputs)
    return all(any(isclose(n, v, rel_tol=0.0001, abs_tol=0.011) for v in valid) for n in numbers) and all(
        d in allowed_dates for d in dates
    )


def guarded(reply, outputs, fallback):
    if check(reply, outputs):
        return reply, False
    if not check(fallback, outputs):
        raise ValueError("Unsafe fallback numeric output")
    return fallback, True
