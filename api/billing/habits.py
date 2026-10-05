"""Customer purchase rhythms: which loyalty-linked customers come back for which product, and how often."""

from collections import Counter, defaultdict
from datetime import date, timedelta
from statistics import median
from billing.generate import AS_OF
from billing.services import receipt
from billing.store import connection, merchant

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
WINDOW = 120
MIN_VISITS = 5
COVERAGE = 0.6  # a rhythm must show up on at least this share of the occasions it should have


def _every(n):
    return {1: "Every day", 7: "Every week", 14: "Every 2 weeks", 21: "Every 3 weeks", 30: "Every month"}.get(
        n, f"Every {n} days"
    )


def classify(days):
    """Return (kind, label, typical gap in days) for sorted visit dates, or None if there is no rhythm.

    A customer's other purchases on the same bills look irregular, so a rhythm must be exact (same
    weekday, or gaps that are whole multiples of the usual gap) and cover most of its expected visits.
    """
    if len(days) < MIN_VISITS:
        return None
    start = AS_OF - timedelta(days=WINDOW - 1)
    gaps = [(b - a).days for a, b in zip(days, days[1:])]
    gap = int(median(gaps))
    weekdays = Counter(d.weekday() for d in days)
    top, count = weekdays.most_common(1)[0]
    occasions = sum(1 for n in range(WINDOW) if (start + timedelta(days=n)).weekday() == top)
    if count / len(days) >= 0.9 and gap >= 6 and len(days) >= COVERAGE * occasions:
        return "weekday", f"Every {DAYS[top]}", 7
    if gap <= 1:
        if not any(d.weekday() >= 5 for d in days):
            weekdays_in_window = sum(1 for n in range(WINDOW) if (start + timedelta(days=n)).weekday() < 5)
            return ("weekdays", "Weekdays", 1) if len(days) >= COVERAGE * weekdays_in_window else None
        return ("daily", "Every day", 1) if len(days) >= COVERAGE * WINDOW else None
    exact = sum(1 for g in gaps if g % gap == 0) / len(gaps)
    if exact >= 0.85 and len(days) >= COVERAGE * WINDOW / gap:
        return "interval", _every(gap), gap
    return None


def customer_habits(mid):
    start = AS_OF - timedelta(days=WINDOW - 1)
    with connection() as db:
        shop = merchant(mid, db)
        names = {p["id"]: p["name"] for p in shop["products"]}
        visits = defaultdict(set)
        for customer, product, day in db.execute(
            "SELECT b.customer, l.product, substr(b.timestamp,1,10) FROM bills b JOIN lines l ON l.bill=b.id "
            "WHERE b.merchant=? AND b.customer IS NOT NULL AND b.timestamp>=? AND b.timestamp<?",
            (mid, str(start), str(AS_OF + timedelta(days=1))),
        ):
            visits[(customer, product)].add(date.fromisoformat(day))
    habits = []
    for (customer, product), days in visits.items():
        found = classify(sorted(days))
        if not found:
            continue
        kind, label, gap = found
        last = max(days)
        since = (AS_OF - last).days
        habits.append(
            dict(
                customer=customer,
                member=customer.rsplit("-", 1)[-1],
                product=product,
                product_name=names[product],
                rhythm=kind,
                cadence=label,
                gap_days=gap,
                visits=len(days),
                last_visit=str(last),
                days_since_last=since,
                status="due back" if since > gap + 1 else "on rhythm",
            )
        )
    habits.sort(key=lambda h: (h["gap_days"], -h["visits"], h["member"]))
    by_product = Counter(h["product_name"] for h in habits)
    grouped = defaultdict(list)
    for h in habits:
        grouped[(h["product"], h["cadence"])].append(h)
    groups = sorted(
        (
            dict(
                product=p,
                product_name=rows[0]["product_name"],
                cadence=c,
                rhythm=rows[0]["rhythm"],
                gap_days=rows[0]["gap_days"],
                customers=len(rows),
                due_back=sum(1 for r in rows if r["status"] == "due back"),
                members=[r["member"] for r in rows],
            )
            for (p, c), rows in grouped.items()
        ),
        key=lambda g: (-g["customers"], g["gap_days"], g["product_name"]),
    )
    summary = dict(
        groups=len(groups),
        regular_customers=len({h["customer"] for h in habits}),
        habits=len(habits),
        due_back=sum(1 for h in habits if h["status"] == "due back"),
        daily=sum(1 for h in habits if h["rhythm"] in ("daily", "weekdays")),
        weekly=sum(1 for h in habits if h["rhythm"] == "weekday"),
        products=[{"name": n, "regulars": c} for n, c in by_product.most_common()],
    )
    return dict(
        merchant=mid,
        window=[str(start), str(AS_OF)],
        habits=habits,
        groups=groups,
        summary=summary,
        receipt=receipt(
            {"merchant": mid, "window": [str(start), str(AS_OF)], "source": "billing.sqlite3: bills.customer + lines"},
            f"A rhythm needs at least {MIN_VISITS} distinct visit days for one customer and one product in {WINDOW} days, "
            f"covering at least {int(COVERAGE * 100)}% of the visits it should have; label = the same weekday, weekdays only, "
            "or a stable gap between visits (whole multiples of the median gap)",
            summary,
            [
                "Only loyalty-linked bills can be followed; anonymous bills are not attributed to anyone.",
                "Members are pseudonymous synthetic loyalty IDs. No names, phone numbers or demographics are inferred.",
                "'Due back' means more than one day beyond the customer's usual gap since the last visit; it is not a prediction of churn.",
            ],
        ),
    )
