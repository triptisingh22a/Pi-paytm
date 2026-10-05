"""What Pi can say about a shop that only shares payments (amount + time), with no item-level bills.

Everything here is computed from bill totals and timestamps alone; product, stock, cost and customer
fields are never read. The capability list says plainly what that data cannot support.
"""

from collections import defaultdict
from datetime import date, timedelta
from math import sqrt
from statistics import mean, pstdev
from billing.generate import AS_OF
from billing.services import receipt
from billing.store import connection, merchant

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

CAPABILITIES = [
    # id, label, needs, available with payments only
    ("takings", "Daily and weekly takings", "Payment amounts and times", True),
    ("peak", "Peak hours and busy weekdays", "Payment times", True),
    ("outlook", "Next-7-day inflow outlook", "Several weeks of payment history", True),
    ("sellers", "Best and slowest sellers", "Item-level bills", False),
    ("restock", "Replenish-soon list and top-up quantities", "Item-level bills + supplier bills for stock", False),
    ("rhythms", "Regular customers and their buying rhythm", "Item-level bills with a customer or loyalty ID", False),
    ("margin", "Contribution after item costs", "Item costs (supplier bills)", False),
    ("twin", "Digital twin: what if I swap or restock a product", "Item-level bills + supplier bills", False),
]


def _hour(h):
    return f"{(h + 11) % 12 + 1} {'AM' if h < 12 else 'PM'}"


def payments_only(mid):
    start = AS_OF - timedelta(days=55)
    with connection() as db:
        shop = merchant(mid, db)
        rows = db.execute(
            "SELECT b.timestamp, SUM(l.qty*l.price) FROM bills b JOIN lines l ON l.bill=b.id "
            "WHERE b.merchant=? AND b.timestamp>=? AND b.timestamp<? GROUP BY b.id",
            (mid, str(start), str(AS_OF + timedelta(days=1))),
        ).fetchall()
    revenue, count, hours = defaultdict(float), defaultdict(int), defaultdict(float)
    for stamp, amount in rows:
        day = date.fromisoformat(stamp[:10])
        revenue[day] += amount
        count[day] += 1
        if day > AS_OF - timedelta(days=28):
            hours[int(stamp[11:13])] += amount
    days = [AS_OF - timedelta(days=n) for n in range(55, -1, -1)]
    series = [revenue.get(d, 0.0) for d in days]
    last7, prior7 = sum(series[-7:]), sum(series[-14:-7])
    change = (last7 / prior7 - 1) if prior7 else 0.0
    by_weekday = defaultdict(list)
    for d, v in zip(days, series):
        by_weekday[d.weekday()].append(v)
    averages = {w: mean(v) for w, v in by_weekday.items()}
    busiest, quietest = max(averages, key=averages.get), min(averages, key=averages.get)
    total_hours = sum(hours.values()) or 1
    peak = [
        {"hour": _hour(h), "share_fraction": round(v / total_hours, 3)}
        for h, v in sorted(hours.items(), key=lambda kv: kv[1], reverse=True)[:3]
    ]
    expected, variance = 0.0, 0.0
    for n in range(1, 8):
        history = by_weekday[(AS_OF + timedelta(days=n)).weekday()][-4:]
        expected += mean(history)
        variance += pstdev(history) ** 2
    spread = sqrt(variance)
    result = dict(
        merchant=mid,
        name=shop["name"],
        window=[str(start), str(AS_OF)],
        chart=[{"label": d.strftime("%d %b"), "revenue": round(v)} for d, v in zip(days[-28:], series[-28:])],
        last7=round(last7),
        prior7=round(prior7),
        change_fraction=round(abs(change), 3),
        change_direction="up" if change >= 0 else "down",
        payments_7d=sum(count[d] for d in days[-7:]),
        busiest_day=DAYS[busiest],
        busiest_day_avg=round(averages[busiest]),
        quietest_day=DAYS[quietest],
        quietest_day_avg=round(averages[quietest]),
        peak_hours=peak,
        outlook=dict(expected=round(expected), low=round(max(expected - spread, 0)), high=round(expected + spread)),
        capabilities=[dict(id=i, label=name, needs=n, available=a) for i, name, n, a in CAPABILITIES],
    )
    result["receipt"] = receipt(
        {"merchant": mid, "window": result["window"], "fields_used": ["payment time", "payment amount"]},
        "Takings = sum of payment amounts per day; outlook = sum over the next 7 weekdays of the average of the last 4 "
        "same weekdays, with a one-standard-deviation band",
        {k: result[k] for k in ("last7", "prior7", "change_fraction", "payments_7d", "busiest_day_avg", "quietest_day_avg", "outlook", "peak_hours")},
        [
            "Uses payment amount and time only. Products, stock, costs and customers are not read.",
            "The outlook repeats recent weekday patterns; it does not know about festivals, promotions or stock-outs.",
            "Payments are not visitor counts: people who browse or pay by other means are not seen.",
        ],
    )
    result["receipt"]["data_tier"] = "A"
    result["receipt"]["data_quality_flags"] = ["SIMULATED_DATA", "PAYMENTS_ONLY"]
    return result
