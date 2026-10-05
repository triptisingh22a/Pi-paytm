import copy
import json
from app.config import DATA
from simulate.generator import generate


class PaytmPOSAdapter:
    """SIMULATED feed. Never connects to Paytm. Latent ground truth never enters engine inputs."""

    def __init__(self):
        if not (DATA / "shops.json").exists():
            generate()
        self.bundle = json.loads((DATA / "shops.json").read_text())

    def merchant(self, merchant, tier="B"):
        shop = copy.deepcopy(self.bundle["shops"][merchant])
        for sku in shop["skus"]:
            for row in sku["history"]:
                row.pop("latent_demand", None)
        shop["payments"] = [
            round(sum(s["price"] * s["history"][i]["sales"] for s in shop["skus"]), 2) for i in range(365)
        ]
        shop["data_tier"] = tier
        if tier == "A":
            shop["skus"] = []
            shop.pop("customer_cohorts", None)
            shop.pop("customer_history", None)
        return shop
