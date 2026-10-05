"""Readable, portable transaction extracts alongside the canonical SQLite demo database."""

import csv
import gzip
import json
import sqlite3
from pathlib import Path

root = Path(__file__).resolve().parents[1]
db = sqlite3.connect(root / "data/billing.sqlite3")
db.row_factory = sqlite3.Row
out = root / "data/exports"
out.mkdir(exist_ok=True)
queries = {
    "pos_lines.csv.gz": """SELECT b.merchant,b.id bill_id,b.timestamp,b.customer loyalty_id,b.profile basket_profile,l.product canonical_sku,l.qty quantity,l.price realized_unit_price,l.cost supplied_unit_cost FROM bills b JOIN lines l ON l.bill=b.id ORDER BY b.timestamp,b.id""",
    "stock_arrivals.csv.gz": "SELECT * FROM stock_events ORDER BY timestamp",
    "daily_availability.csv.gz": "SELECT * FROM daily ORDER BY day,merchant,product",
    "lookalike_weekly_facts.csv.gz": "SELECT * FROM peer_weeks ORDER BY week,kind,peer,product",
}
for filename, query in queries.items():
    cursor = db.execute(query)
    with gzip.open(out / filename, "wt", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([c[0] for c in cursor.description])
        writer.writerows(cursor)
rows = []
for m in db.execute("SELECT * FROM merchants"):
    mid = m["id"]
    rows.append(
        {
            "merchant": mid,
            "name": m["name"],
            "bills": db.execute(
                "SELECT COUNT(*) FROM bills WHERE merchant=?", (mid,)
            ).fetchone()[0],
            "line_items": db.execute(
                "SELECT COUNT(*) FROM lines l JOIN bills b ON b.id=l.bill WHERE b.merchant=?",
                (mid,),
            ).fetchone()[0],
            "stock_events": db.execute(
                "SELECT COUNT(*) FROM stock_events WHERE merchant=?", (mid,)
            ).fetchone()[0],
            "catalogue_items": len(json.loads(m["products"])),
            "donor_shops": 40,
            "products": json.loads(m["products"]),
            "ingredients_kg": json.loads(m["ingredients"]),
        }
    )
manifest = {
    "simulated": True,
    "start": "2025-10-03",
    "end": "2026-10-02",
    "days": 365,
    "seed": 731,
    "timezone": "Asia/Kolkata (+05:30)",
    "files": list(queries),
    "total_bills": db.execute("SELECT COUNT(*) FROM bills").fetchone()[0],
    "total_line_items": db.execute("SELECT COUNT(*) FROM lines").fetchone()[0],
    "donor_count": 280,
    "peer_week_facts": db.execute("SELECT COUNT(*) FROM peer_weeks").fetchone()[0],
    "schema_note": "Seven focal shops have complete item-level bills and stock arrivals. 280 donors have generated weekly sufficient statistics from simulated bill opportunities, not stored raw donor invoices.",
    "availability_note": "Daily exposure counts synthetic completed-bill opportunities at which each item was available. Real POS deployments need an availability/stockout integration, not just invoice zeros.",
    "customer_note": "65% chance of a synthetic pseudonymous loyalty ID on a bill; no demographic or all-visitor inference.",
    "merchants": rows,
}
(root / "data/billing_manifest.json").write_text(json.dumps(manifest, indent=2))
print(
    json.dumps(
        {
            k: manifest[k]
            for k in (
                "total_bills",
                "total_line_items",
                "donor_count",
                "peer_week_facts",
            )
        }
    )
)
